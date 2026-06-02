"""
구글 스프레드시트 연동 모듈
"""
import gspread
from google.oauth2.service_account import Credentials


class SheetHandler:
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    def __init__(self, credentials_file, spreadsheet_id, sheet_name):
        self.credentials_file = credentials_file
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.client = None
        self.sheet = None
        self._strikethrough_cache = None
        
    def connect(self):
        """스프레드시트 연결"""
        try:
            creds = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=self.SCOPES
            )
            self.client = gspread.authorize(creds)
            spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            self.sheet = spreadsheet.worksheet(self.sheet_name)
            self._strikethrough_cache = None  # 캐시 초기화
            return True
        except Exception as e:
            print(f"스프레드시트 연결 오류: {e}")
            return False
    
    def get_strikethrough_rows(self, force_refresh=False):
        """취소선(strikethrough)이 적용된 행 번호 집합 반환 (캐시 사용)"""
        if self._strikethrough_cache is not None and not force_refresh:
            return self._strikethrough_cache
        
        try:
            spreadsheet = self.sheet.spreadsheet
            sheet_title = self.sheet.title
            
            # M열(아티스트)의 서식 정보만 가져오기 — 취소선은 행 전체에 적용되므로 한 열만 확인
            url = f'https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet.id}'
            params = {
                'ranges': f"'{sheet_title}'!M:M",
                'fields': 'sheets.data.rowData.values.userEnteredFormat.textFormat.strikethrough',
                'includeGridData': 'true'
            }
            
            response = spreadsheet.client.request('get', url, params=params)
            
            # gspread 버전에 따라 response 형태가 다름
            if hasattr(response, 'json'):
                data = response.json()
            else:
                data = response
            
            strikethrough_rows = set()
            
            for sheet_data in data.get('sheets', []):
                for grid_data in sheet_data.get('data', []):
                    for row_idx, row_data in enumerate(grid_data.get('rowData', []), start=1):
                        for val in row_data.get('values', []):
                            fmt = val.get('userEnteredFormat', {})
                            if fmt.get('textFormat', {}).get('strikethrough', False):
                                strikethrough_rows.add(row_idx)
                                break
            
            self._strikethrough_cache = strikethrough_rows
            print(f"취소선 행 {len(strikethrough_rows)}개 발견")
            return strikethrough_rows
            
        except Exception as e:
            print(f"취소선 행 조회 오류: {e}")
            import traceback
            traceback.print_exc()
            self._strikethrough_cache = set()
            return set()
    
    def clear_strikethrough_cache(self):
        """취소선 캐시 초기화 (목록 새로고침 시 호출)"""
        self._strikethrough_cache = None
    
    def column_letter_to_index(self, letter):
        """열 문자를 인덱스로 변환 (A=1, B=2, ...)"""
        result = 0
        for char in letter.upper():
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result
    
    def find_row_by_artist_album(self, artist, album, artist_col='M', album_col='N'):
        """아티스트명과 앨범명으로 행 찾기 (정확 → 부분 매칭, 취소선 제외)
        한영 병기 대응: 시트 "우예린(Woo Yerin)" ↔ 슬랙 "우예린" / "Woo Yerin" 둘 다 매칭.
        """
        try:
            all_data = self.sheet.get_all_values()
            strikethrough = self.get_strikethrough_rows()

            artist_idx = self.column_letter_to_index(artist_col) - 1
            album_idx = self.column_letter_to_index(album_col) - 1
            a_low = artist.lower().strip()
            al_low = album.lower().strip()

            # 1차: 정확 매칭
            for row_num, row in enumerate(all_data, start=1):
                if row_num in strikethrough:
                    continue
                if len(row) > max(artist_idx, album_idx):
                    row_artist = row[artist_idx].strip().lower()
                    row_album = row[album_idx].strip().lower()
                    if row_artist == a_low and row_album == al_low:
                        return row_num

            # 2차: 부분 매칭 (한영 병기 등) — 양방향 contains
            for row_num, row in enumerate(all_data, start=1):
                if row_num in strikethrough:
                    continue
                if len(row) > max(artist_idx, album_idx):
                    row_artist = row[artist_idx].strip().lower()
                    row_album = row[album_idx].strip().lower()
                    artist_match = (a_low in row_artist or row_artist in a_low)
                    album_match = (al_low in row_album or row_album in al_low)
                    if artist_match and album_match and row_artist and row_album:
                        print(f"부분 매칭: '{artist}' - '{album}' → 행 {row_num} ({row[artist_idx]} - {row[album_idx]})")
                        return row_num

            return None
        except Exception as e:
            print(f"행 검색 오류: {e}")
            return None
    
    def find_all_rows_by_artist_album(self, artist, album, artist_col='M', album_col='N'):
        """아티스트명과 앨범명으로 모든 행 찾기 (취소선 제외)"""
        try:
            all_data = self.sheet.get_all_values()
            strikethrough = self.get_strikethrough_rows()
            
            artist_idx = self.column_letter_to_index(artist_col) - 1
            album_idx = self.column_letter_to_index(album_col) - 1
            
            matching_rows = []
            
            for row_num, row in enumerate(all_data, start=1):
                if row_num in strikethrough:
                    continue
                if len(row) > max(artist_idx, album_idx):
                    row_artist = row[artist_idx].strip()
                    row_album = row[album_idx].strip()
                    
                    if (row_artist.lower() == artist.lower() and 
                        row_album.lower() == album.lower()):
                        matching_rows.append(row_num)
            
            return matching_rows
        except Exception as e:
            print(f"행 검색 오류: {e}")
            return []
    
    def get_cell_value(self, row, col):
        """특정 셀 값 가져오기"""
        try:
            cell = f"{col}{row}"
            return self.sheet.acell(cell).value
        except Exception as e:
            print(f"셀 읽기 오류: {e}")
            return None
    
    def set_cell_value(self, row, col, value):
        """특정 셀에 값 입력"""
        try:
            cell = f"{col}{row}"
            self.sheet.update_acell(cell, value)
            return True
        except Exception as e:
            print(f"셀 쓰기 오류: {e}")
            return False
    
    def check_upc_exists(self, row, upc_col='H'):
        """UPC 값이 이미 있는지 확인"""
        value = self.get_cell_value(row, upc_col)
        return value is not None and value.strip() != ''
    
    def write_upc(self, row, upc_value, upc_col='H'):
        """UPC 값 입력 (단일 행)"""
        return self.set_cell_value(row, upc_col, upc_value)
    
    def write_upc_to_all_rows(self, artist, album, upc_value, artist_col='M', album_col='N', upc_col='H'):
        """
        같은 아티스트/앨범의 모든 행에 UPC 입력 (여러 트랙 처리)
        
        Returns:
            dict: {
                'success': bool,
                'rows_updated': list,
                'message': str
            }
        """
        try:
            # 모든 매칭 행 찾기
            rows = self.find_all_rows_by_artist_album(artist, album, artist_col, album_col)
            
            if not rows:
                return {
                    'success': False,
                    'rows_updated': [],
                    'message': f"'{artist} - {album}'을(를) 찾을 수 없습니다."
                }
            
            # 모든 행에 UPC 입력
            updated_rows = []
            for row in rows:
                if self.write_upc(row, upc_value, upc_col):
                    updated_rows.append(row)
                    print(f"  행 {row}에 UPC 입력 완료")
            
            return {
                'success': True,
                'rows_updated': updated_rows,
                'message': f"총 {len(updated_rows)}개 행에 UPC '{upc_value}' 입력 완료 (행: {updated_rows})"
            }
            
        except Exception as e:
            print(f"UPC 입력 오류: {e}")
            return {
                'success': False,
                'rows_updated': [],
                'message': f"UPC 입력 오류: {e}"
            }
    
    def validate_submission(self, artist, album, artist_col='M', album_col='N', upc_col='H'):
        """
        슬랙 메시지의 아티스트/앨범 정보를 스프레드시트와 교차검증
        
        Returns:
            dict: {
                'valid': bool,
                'row': int or None,
                'upc_exists': bool,
                'message': str
            }
        """
        # 행 찾기
        row = self.find_row_by_artist_album(artist, album, artist_col, album_col)
        
        if row is None:
            return {
                'valid': False,
                'row': None,
                'upc_exists': False,
                'message': f"스프레드시트에서 '{artist} - {album}'을(를) 찾을 수 없습니다."
            }
        
        # UPC 확인
        upc_exists = self.check_upc_exists(row, upc_col)
        
        if upc_exists:
            existing_upc = self.get_cell_value(row, upc_col)
            return {
                'valid': True,
                'row': row,
                'upc_exists': True,
                'existing_upc': existing_upc,
                'message': f"'{artist} - {album}' (행 {row})에 이미 UPC가 존재합니다: {existing_upc}"
            }
        
        return {
            'valid': True,
            'row': row,
            'upc_exists': False,
            'message': f"'{artist} - {album}' (행 {row}) 확인 완료. UPC 발급이 필요합니다."
        }
    
    def get_row_data(self, row, columns_map):
        """
        특정 행의 여러 컬럼 데이터 가져오기
        
        Args:
            row: 행 번호
            columns_map: {'key': 'column_letter'} 형태
        
        Returns:
            dict: {'key': 'value'} 형태
        """
        result = {}
        for key, col in columns_map.items():
            result[key] = self.get_cell_value(row, col)
        return result
    
    def test_connection(self):
        """연결 테스트"""
        try:
            if self.connect():
                # 시트 이름 확인
                title = self.sheet.title
                row_count = self.sheet.row_count
                return {
                    'success': True,
                    'sheet_title': title,
                    'row_count': row_count
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


    # ==========================================
    # MIMS 관련 메서드
    # ==========================================
    
    # MIMS 열 매핑
    MIMS_COLUMNS = {
        # 입력용 컬럼
        'artist': 'M',           # 아티스트명
        'album': 'N',            # 앨범명
        'release_date': 'O',     # 발매일
        'genre': 'T',            # 장르
        'upc': 'H',              # UPC (바코드)
        'album_code': 'K',       # 권리사앨범코드 (입력)
        'track_code': 'L',       # 권리자곡관리코드 (입력)
        'track_name': 'AA',      # 곡명
        'featuring': 'AC',       # 피처링
        'producer': 'AF',        # 제작사
        'lyricist': 'AJ',        # 작사
        'composer': 'AK',        # 작곡
        'arranger': 'AL',        # 편곡
        'duration': 'AQ',        # 재생시간
        'is_title': 'Z',         # 대표곡 여부 (Y)
        # 출력용 컬럼
        'isrc': 'I',             # ISRC (저장)
        'uci': 'J',              # UCI (저장)
    }
    
    def get_album_tracks_data(self, artist, album):
        """
        앨범의 모든 트랙 정보 가져오기 (MIMS 등록용)
        
        Returns:
            dict: {
                'album_data': {...},
                'tracks': [{...}, ...]
            }
        """
        try:
            # 모든 데이터 가져오기
            all_data = self.sheet.get_all_values()
            strikethrough = self.get_strikethrough_rows()
            
            # 열 인덱스
            cols = self.MIMS_COLUMNS
            artist_idx = self.column_letter_to_index(cols['artist']) - 1
            album_idx = self.column_letter_to_index(cols['album']) - 1
            
            tracks = []
            album_data = None
            
            for row_num, row in enumerate(all_data, start=1):
                if row_num in strikethrough:
                    continue
                if len(row) <= max(artist_idx, album_idx):
                    continue
                    
                row_artist = row[artist_idx].strip()
                row_album = row[album_idx].strip()
                
                if row_artist.lower() == artist.lower() and row_album.lower() == album.lower():
                    # 첫 번째 행에서 앨범 정보 추출
                    if album_data is None:
                        album_data = {
                            'album_name': self._get_cell_value_from_row(row, cols['album']),
                            'artist_name': self._get_cell_value_from_row(row, cols['artist']),
                            'release_date': self._get_cell_value_from_row(row, cols['release_date']),
                            'genre': self._get_cell_value_from_row(row, cols['genre']),
                            'producer': self._get_cell_value_from_row(row, cols['producer']),  # AF열
                            'upc': self._get_cell_value_from_row(row, cols['upc']),  # H열
                            'album_code': self._get_cell_value_from_row(row, cols['album_code']),  # K열 (권리사앨범코드)
                        }
                    
                    # 트랙 정보 추출
                    track_data = {
                        'row_number': row_num,
                        'track_name': self._get_cell_value_from_row(row, cols['track_name']),  # AA열
                        'artist_name': self._get_cell_value_from_row(row, cols['artist']),
                        'genre': self._get_cell_value_from_row(row, cols['genre']),
                        'duration': self._get_cell_value_from_row(row, cols['duration']),  # AQ열
                        'track_code': self._get_cell_value_from_row(row, cols['track_code']),  # L열 (권리자곡관리코드)
                        'is_title': self._get_cell_value_from_row(row, cols['is_title']),  # Z열 (대표곡)
                        'lyricist': self._get_cell_value_from_row(row, cols['lyricist']),  # AJ열
                        'composer': self._get_cell_value_from_row(row, cols['composer']),  # AK열
                        'arranger': self._get_cell_value_from_row(row, cols['arranger']),  # AL열
                        'featuring': self._get_cell_value_from_row(row, cols['featuring']),  # AC열
                    }
                    tracks.append(track_data)
            
            if not album_data:
                return None
            
            album_data['track_count'] = len(tracks)
            
            return {
                'album_data': album_data,
                'tracks': tracks
            }
            
        except Exception as e:
            print(f"앨범 트랙 데이터 조회 오류: {e}")
            return None
    
    def _get_cell_value_from_row(self, row, col_letter):
        """행에서 특정 열의 값 가져오기"""
        try:
            col_idx = self.column_letter_to_index(col_letter) - 1
            if col_idx < len(row):
                return row[col_idx].strip()
            return ''
        except:
            return ''
    
    def check_isrc_exists(self, row, isrc_col='I'):
        """ISRC 값이 이미 있는지 확인"""
        value = self.get_cell_value(row, isrc_col)
        return value is not None and value.strip() != ''
    
    def write_mims_data_to_row(self, row, isrc=None, uci=None, album_code=None, track_code=None):
        """
        단일 행에 MIMS 데이터 저장
        
        Args:
            row: 행 번호
            isrc: ISRC 코드
            uci: UCI 코드
            album_code: 앨범코드
            track_code: 곡코드
        """
        try:
            cols = self.MIMS_COLUMNS
            
            if isrc:
                self.set_cell_value(row, cols['isrc'], isrc)
                print(f"  행 {row}: ISRC = {isrc}")
            
            if uci:
                self.set_cell_value(row, cols['uci'], uci)
                print(f"  행 {row}: UCI = {uci}")
            
            if album_code:
                self.set_cell_value(row, cols['album_code'], album_code)
                print(f"  행 {row}: 앨범코드 = {album_code}")
            
            # track_code(L열, 권리자곡관리코드)는 기록하지 않음 — 별도 관리 중
            
            return True
        except Exception as e:
            print(f"MIMS 데이터 저장 오류: {e}")
            return False
    
    def write_mims_data_to_album(self, artist, album, mims_data):
        """
        앨범의 모든 트랙에 MIMS 데이터 저장
        
        매칭 우선순위:
        1. 곡명(track_name) 매칭 — MIMS 트랙 곡명과 스프레드시트 AA열 비교
        2. 순서 매칭 (폴백) — 곡명이 없거나 매칭 실패 시 행 순서대로
        
        Args:
            artist: 아티스트명
            album: 앨범명
            mims_data: {
                'album_code': 앨범코드,
                'tracks': [
                    {'track_code': 곡코드, 'isrc': ISRC, 'uci': UCI, 'track_name': 곡명},
                    ...
                ]
            }
        
        Returns:
            dict: {'success': bool, 'rows_updated': list, 'message': str}
        """
        try:
            rows = self.find_all_rows_by_artist_album(artist, album)
            
            if not rows:
                return {
                    'success': False,
                    'rows_updated': [],
                    'message': f"'{artist} - {album}'을(를) 찾을 수 없습니다."
                }
            
            album_code = mims_data.get('album_code')
            tracks = mims_data.get('tracks', [])
            
            # 곡명 매칭 가능 여부 판단
            has_track_names = any(t.get('track_name', '').strip() for t in tracks)
            
            # row → track_data 매핑 결과
            row_to_track = {}
            matched_by_name = 0
            
            if has_track_names:
                cols = self.MIMS_COLUMNS
                
                # 스프레드시트 각 행의 곡명 읽기
                row_names = {}
                for row_num in rows:
                    try:
                        val = self.get_cell_value(row_num, cols['track_name'])
                        row_names[row_num] = (val or '').strip()
                    except:
                        row_names[row_num] = ''
                
                used_track_indices = set()
                used_rows = set()
                
                # 1차: 정확히 일치
                for ti, track in enumerate(tracks):
                    mims_name = (track.get('track_name') or '').strip()
                    if not mims_name:
                        continue
                    for row_num in rows:
                        if row_num in used_rows:
                            continue
                        if row_names[row_num] == mims_name:
                            row_to_track[row_num] = track
                            used_rows.add(row_num)
                            used_track_indices.add(ti)
                            matched_by_name += 1
                            print(f"  곡명 매칭(정확): '{mims_name}' → 행 {row_num}")
                            break
                
                # 2차: 공백 제거 + 소문자 포함 관계
                for ti, track in enumerate(tracks):
                    if ti in used_track_indices:
                        continue
                    mims_name = (track.get('track_name') or '').strip()
                    if not mims_name:
                        continue
                    mims_clean = mims_name.replace(' ', '').lower()
                    for row_num in rows:
                        if row_num in used_rows:
                            continue
                        sheet_clean = row_names[row_num].replace(' ', '').lower()
                        if sheet_clean and (mims_clean in sheet_clean or sheet_clean in mims_clean):
                            row_to_track[row_num] = track
                            used_rows.add(row_num)
                            used_track_indices.add(ti)
                            matched_by_name += 1
                            print(f"  곡명 매칭(유사): '{mims_name}' ≈ '{row_names[row_num]}' → 행 {row_num}")
                            break
                
                # 3차: 매칭 안 된 행/트랙은 순서대로 폴백
                remaining_rows = [r for r in rows if r not in used_rows]
                remaining_tracks = [tracks[i] for i in range(len(tracks)) if i not in used_track_indices]
                
                for i, row_num in enumerate(remaining_rows):
                    if i < len(remaining_tracks):
                        row_to_track[row_num] = remaining_tracks[i]
                        print(f"  순서 폴백: 트랙 {remaining_tracks[i].get('track_name', '?')} → 행 {row_num}")
            else:
                # 곡명 없음 → 순서대로 매칭
                for i, row_num in enumerate(rows):
                    if i < len(tracks):
                        row_to_track[row_num] = tracks[i]
            
            # 실제 저장
            updated_rows = []
            for row_num in rows:
                track_data = row_to_track.get(row_num, {})
                if not track_data:
                    continue
                
                self.write_mims_data_to_row(
                    row=row_num,
                    isrc=track_data.get('isrc'),
                    uci=track_data.get('uci'),
                    album_code=album_code,
                    track_code=track_data.get('track_code')
                )
                updated_rows.append(row_num)
            
            matched_by_order = len(updated_rows) - matched_by_name
            msg = f"총 {len(updated_rows)}개 행 저장 (곡명매칭: {matched_by_name}, 순서매칭: {matched_by_order})"
            print(f"  {msg}")
            
            return {
                'success': True,
                'rows_updated': updated_rows,
                'message': msg
            }
            
        except Exception as e:
            print(f"MIMS 데이터 저장 오류: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'rows_updated': [],
                'message': f"MIMS 데이터 저장 오류: {e}"
            }
    
    def get_albums_without_isrc(self, limit=500):
        """
        ISRC가 없는 앨범 목록 가져오기 (올해 발매분만)
        
        Returns:
            list: [{'artist': 아티스트, 'album': 앨범, 'row': 첫번째행}, ...]
        """
        try:
            from datetime import datetime
            current_year = str(datetime.now().year)
            
            all_data = self.sheet.get_all_values()
            strikethrough = self.get_strikethrough_rows()
            
            cols = self.MIMS_COLUMNS
            artist_idx = self.column_letter_to_index(cols['artist']) - 1
            album_idx = self.column_letter_to_index(cols['album']) - 1
            isrc_idx = self.column_letter_to_index(cols['isrc']) - 1
            upc_idx = self.column_letter_to_index(cols['upc']) - 1
            release_date_idx = self.column_letter_to_index(cols['release_date']) - 1
            album_code_idx = self.column_letter_to_index(cols['album_code']) - 1   # K열
            track_code_idx = self.column_letter_to_index(cols['track_code']) - 1   # L열
            
            albums_found = {}
            
            for row_num, row in enumerate(all_data, start=1):
                if row_num == 1 or row_num in strikethrough:
                    continue
                    
                if len(row) <= max(artist_idx, album_idx, isrc_idx):
                    continue
                
                artist = row[artist_idx].strip()
                album = row[album_idx].strip()
                isrc = row[isrc_idx].strip() if isrc_idx < len(row) else ''
                upc = row[upc_idx].strip() if upc_idx < len(row) else ''
                release_date = row[release_date_idx].strip() if release_date_idx < len(row) else ''
                album_code = row[album_code_idx].strip() if album_code_idx < len(row) else ''
                track_code = row[track_code_idx].strip() if track_code_idx < len(row) else ''
                
                if not artist or not album:
                    continue
                
                # 올해 발매분만
                if not release_date or current_year not in release_date:
                    continue
                
                # UPC + 앨범코드 + 곡코드가 있고, ISRC가 없는 경우만
                if upc and album_code and track_code and not isrc:
                    key = f"{artist}|{album}"
                    if key not in albums_found:
                        albums_found[key] = {
                            'artist': artist,
                            'album': album,
                            'row': row_num,
                            'upc': upc,
                            'release_date': release_date
                        }
                
                if len(albums_found) >= limit:
                    break
            
            return list(albums_found.values())
            
        except Exception as e:
            print(f"앨범 목록 조회 오류: {e}")
            return []
    
    def get_albums_without_uci(self, limit=500):
        """
        ISRC는 있지만 UCI가 없는 앨범 목록 가져오기 (올해 발매분만)
        
        Returns:
            list: [{'artist': 아티스트, 'album': 앨범, 'row': 첫번째행, 'upc': UPC}, ...]
        """
        try:
            from datetime import datetime
            current_year = str(datetime.now().year)
            
            all_data = self.sheet.get_all_values()
            strikethrough = self.get_strikethrough_rows()
            
            cols = self.MIMS_COLUMNS
            artist_idx = self.column_letter_to_index(cols['artist']) - 1
            album_idx = self.column_letter_to_index(cols['album']) - 1
            isrc_idx = self.column_letter_to_index(cols['isrc']) - 1
            uci_idx = self.column_letter_to_index(cols['uci']) - 1
            upc_idx = self.column_letter_to_index(cols['upc']) - 1
            release_date_idx = self.column_letter_to_index(cols['release_date']) - 1
            album_code_idx = self.column_letter_to_index(cols['album_code']) - 1   # K열
            track_code_idx = self.column_letter_to_index(cols['track_code']) - 1   # L열
            
            albums_found = {}
            
            for row_num, row in enumerate(all_data, start=1):
                if row_num == 1 or row_num in strikethrough:
                    continue
                    
                if len(row) <= max(artist_idx, album_idx, isrc_idx, uci_idx):
                    continue
                
                artist = row[artist_idx].strip()
                album = row[album_idx].strip()
                isrc = row[isrc_idx].strip() if isrc_idx < len(row) else ''
                uci = row[uci_idx].strip() if uci_idx < len(row) else ''
                upc = row[upc_idx].strip() if upc_idx < len(row) else ''
                release_date = row[release_date_idx].strip() if release_date_idx < len(row) else ''
                album_code = row[album_code_idx].strip() if album_code_idx < len(row) else ''
                track_code = row[track_code_idx].strip() if track_code_idx < len(row) else ''
                
                if not artist or not album:
                    continue
                
                # 올해 발매분만
                if not release_date or current_year not in release_date:
                    continue
                
                # ISRC가 있고, 앨범코드+곡코드가 있고, UCI가 없는 경우
                if isrc and album_code and track_code and not uci:
                    key = f"{artist}|{album}"
                    if key not in albums_found:
                        albums_found[key] = {
                            'artist': artist,
                            'album': album,
                            'row': row_num,
                            'upc': upc,
                            'release_date': release_date
                        }
                
                if len(albums_found) >= limit:
                    break
            
            return list(albums_found.values())
            
        except Exception as e:
            print(f"UCI 미발급 앨범 조회 오류: {e}")
            return []
    
    def get_albums_without_upc(self, limit=10):
        """
        UPC가 없는 앨범 목록 가져오기
        
        Returns:
            list: [{'artist': 아티스트, 'album': 앨범, 'row': 첫번째행, 'release_date': 발매일}, ...]
        """
        try:
            all_data = self.sheet.get_all_values()
            
            cols = self.MIMS_COLUMNS
            artist_idx = self.column_letter_to_index(cols['artist']) - 1
            album_idx = self.column_letter_to_index(cols['album']) - 1
            upc_idx = self.column_letter_to_index(cols['upc']) - 1
            release_date_idx = self.column_letter_to_index(cols['release_date']) - 1
            track_name_idx = self.column_letter_to_index(cols['track_name']) - 1
            
            albums_found = {}
            
            for row_num, row in enumerate(all_data, start=1):
                if row_num == 1:  # 헤더 스킵
                    continue
                    
                if len(row) <= max(artist_idx, album_idx):
                    continue
                
                artist = row[artist_idx].strip()
                album = row[album_idx].strip()
                upc = row[upc_idx].strip() if upc_idx < len(row) else ''
                release_date = row[release_date_idx].strip() if release_date_idx < len(row) else ''
                track_name = row[track_name_idx].strip() if track_name_idx < len(row) else ''
                
                # 아티스트/앨범이 비어있으면 스킵
                if not artist or not album:
                    continue
                
                # UPC가 없는 경우만
                if not upc:
                    key = f"{artist}|{album}"
                    if key not in albums_found:
                        albums_found[key] = {
                            'artist': artist,
                            'album': album,
                            'row': row_num,
                            'release_date': release_date,
                            'track_name': track_name
                        }
                
                if len(albums_found) >= limit:
                    break
            
            return list(albums_found.values())
            
        except Exception as e:
            print(f"UPC 없는 앨범 목록 조회 오류: {e}")
            return []
    
    def write_upc_to_album(self, artist, album, upc):
        """
        앨범에 UPC 저장
        
        Args:
            artist: 아티스트명
            album: 앨범명  
            upc: UPC 코드
        
        Returns:
            dict: {'success': bool, 'rows_updated': list}
        """
        try:
            rows = self.find_all_rows_by_artist_album(artist, album)
            
            if not rows:
                return {
                    'success': False,
                    'rows_updated': [],
                    'message': f"'{artist} - {album}'을(를) 찾을 수 없습니다."
                }
            
            cols = self.MIMS_COLUMNS
            upc_col = cols['upc']
            
            updated_rows = []
            for row in rows:
                self.set_cell_value(row, upc_col, upc)
                updated_rows.append(row)
                print(f"  행 {row}: UPC = {upc}")
            
            return {
                'success': True,
                'rows_updated': updated_rows,
                'message': f"총 {len(updated_rows)}개 행에 UPC 저장 완료"
            }
            
        except Exception as e:
            print(f"UPC 저장 오류: {e}")
            return {
                'success': False,
                'rows_updated': [],
                'message': str(e)
            }


if __name__ == "__main__":
    # 테스트
    handler = SheetHandler(
        credentials_file="credentials/google_credentials.json",
        spreadsheet_id="1gcQUHfCeNBq0G3lzzNsckoe-SeP2rmsWHcee_0JbYHE",
        sheet_name="발매리스트"
    )
    
    result = handler.test_connection()
    print("연결 테스트:", result)
    
    # MIMS 데이터 테스트
    if result.get('success'):
        albums = handler.get_albums_without_isrc(limit=5)
        print("\nISRC 없는 앨범 목록:")
        for album in albums:
            print(f"  - {album['artist']} - {album['album']} (행 {album['row']})")

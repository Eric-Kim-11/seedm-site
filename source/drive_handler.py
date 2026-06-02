"""
구글 드라이브 앨범 이미지 다운로드 모듈
- 공유 드라이브 지원
- 폴더 규칙: "YYYYMMDD 아티스트 앨범명 1200"
- 파일명: "[album art].jpg"
"""
import os
import io
import re
import difflib
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


def _extract_album(folder_name, date_prefix, artist):
    """폴더명('YYYYMMDD ARTIST ALBUM 1200 [라벨]')에서 날짜·아티스트·사이즈코드를 빼고
    앨범명 부분만 근사 추출. 유사도 매칭 비교용."""
    s = folder_name
    if date_prefix:
        s = s.replace(date_prefix, " ")
    if artist:
        s = re.sub(re.escape(artist), " ", s, flags=re.IGNORECASE)
    s = re.sub(r'\b\d{3,4}\b', " ", s)   # 1200/1800/3000 등 사이즈 코드 제거
    return " ".join(s.split()).strip()


class DriveHandler:
    """구글 드라이브 핸들러"""
    
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly'
    ]
    
    # 앨범 아트 공유 드라이브 폴더 ID
    ALBUM_ART_FOLDER_ID = "1Vbe3JeeMrvSFi7TFpWC2xu1yUOSxXKaE"
    
    def __init__(self, credentials_file):
        self.credentials_file = credentials_file
        self.service = None
        
    def connect(self):
        """드라이브 API 연결"""
        try:
            creds = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=self.SCOPES
            )
            self.service = build('drive', 'v3', credentials=creds)
            print("✅ 구글 드라이브 연결 성공")
            return True
        except Exception as e:
            print(f"❌ 구글 드라이브 연결 오류: {e}")
            return False
    
    def search_folder(self, artist_name, album_name, release_date=None, parent_folder_id=None):
        """
        앨범 이미지 폴더 검색 (공유 드라이브 지원)
        
        폴더명 규칙: "20260216 DIAN LOVE 1200"
        - 발매일(YYYYMMDD) + 아티스트 + 앨범명 + 1200
        """
        try:
            if parent_folder_id is None:
                parent_folder_id = self.ALBUM_ART_FOLDER_ID
            
            query = f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder'"
            
            # 공유 드라이브 검색 지원
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
                pageSize=200,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            
            folders = results.get('files', [])
            print(f"🔍 폴더 검색 중... (총 {len(folders)}개 폴더)")
            
            # 검색 키워드 준비 (소문자)
            artist_lower = artist_name.lower().strip()
            album_lower = album_name.lower().strip()
            
            # 발매일 형식 변환 (YYYY-MM-DD 또는 YYYY.MM.DD → YYYYMMDD)
            date_prefix = None
            if release_date:
                date_clean = release_date.replace('-', '').replace('.', '').replace('/', '')[:8]
                if date_clean.isdigit() and len(date_clean) == 8:
                    date_prefix = date_clean
            
            # 1. 발매일 + 아티스트 + 앨범명 정확 매칭
            if date_prefix:
                for folder in folders:
                    folder_name = folder['name']
                    folder_lower = folder_name.lower()
                    
                    # "20260216 DIAN LOVE 1200" 패턴
                    if (date_prefix in folder_name and 
                        artist_lower in folder_lower and 
                        album_lower in folder_lower):
                        print(f"✅ 폴더 찾음 (정확 매칭): {folder_name}")
                        return folder['id']
            
            # 2. 아티스트 + 앨범명 매칭
            for folder in folders:
                folder_name = folder['name']
                folder_lower = folder_name.lower()
                
                if artist_lower in folder_lower and album_lower in folder_lower:
                    print(f"✅ 폴더 찾음 (아티스트+앨범 매칭): {folder_name}")
                    return folder['id']
            
            # 3. 앨범명만 매칭
            for folder in folders:
                folder_name = folder['name']
                folder_lower = folder_name.lower()
                
                if album_lower in folder_lower:
                    print(f"✅ 폴더 찾음 (앨범명 매칭): {folder_name}")
                    return folder['id']

            # 4. 유사도 매칭 (특수문자/오타 대비) — 같은 발매일+아티스트 폴더 한정, 앨범명 80%+
            candidates = [
                f for f in folders
                if artist_lower in f['name'].lower()
                and (not date_prefix or date_prefix in f['name'])
            ]
            best, best_ratio = None, 0.0
            for folder in candidates:
                cand_album = _extract_album(folder['name'], date_prefix, artist_name).lower()
                ratio = difflib.SequenceMatcher(None, album_lower, cand_album).ratio()
                if ratio > best_ratio:
                    best, best_ratio = folder, ratio
            if best and best_ratio >= 0.8:
                print(f"✅ 폴더 찾음 (유사매칭 {best_ratio:.0%}): {best['name']}  ← 시트앨범명 '{album_name}'")
                return best['id']

            print(f"❌ 폴더를 찾을 수 없음: {artist_name} - {album_name}")
            if date_prefix:
                print(f"   (발매일: {date_prefix})")
            
            return None
            
        except Exception as e:
            print(f"❌ 폴더 검색 오류: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def find_album_art(self, folder_id):
        """
        폴더 내 앨범 아트 파일 찾기 (공유 드라이브 지원)
        파일명 규칙: "[album art].jpg"
        """
        try:
            query = f"'{folder_id}' in parents"
            
            # 공유 드라이브 지원
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, mimeType)',
                pageSize=50,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            
            files = results.get('files', [])
            
            # "[album art]" 정확 매칭 우선
            for file in files:
                name_lower = file['name'].lower()
                if '[album art]' in name_lower:
                    print(f"✅ 앨범 아트 찾음: {file['name']}")
                    return file['id'], file['name']
            
            # "album art" 포함
            for file in files:
                name_lower = file['name'].lower()
                if 'album art' in name_lower or 'albumart' in name_lower:
                    print(f"✅ 앨범 아트 찾음: {file['name']}")
                    return file['id'], file['name']
            
            # "cover" 포함
            for file in files:
                name_lower = file['name'].lower()
                if 'cover' in name_lower and name_lower.endswith(('.jpg', '.jpeg', '.png')):
                    print(f"✅ 앨범 아트 찾음: {file['name']}")
                    return file['id'], file['name']
            
            # 이미지 파일 중 첫 번째
            image_types = ['image/jpeg', 'image/png']
            for file in files:
                if file.get('mimeType') in image_types:
                    print(f"✅ 앨범 아트 찾음 (이미지): {file['name']}")
                    return file['id'], file['name']
            
            print("❌ 앨범 아트 파일을 찾을 수 없음")
            return None, None
            
        except Exception as e:
            print(f"❌ 앨범 아트 검색 오류: {e}")
            return None, None
    
    def download_file(self, file_id, destination_path):
        """파일 다운로드 (공유 드라이브 지원)"""
        try:
            # 공유 드라이브 지원
            request = self.service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True
            )
            
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    print(f"다운로드 진행: {int(status.progress() * 100)}%")
            
            # 파일 저장
            fh.seek(0)
            with open(destination_path, 'wb') as f:
                f.write(fh.read())
            
            print(f"✅ 파일 다운로드 완료: {destination_path}")
            return True
            
        except Exception as e:
            print(f"❌ 파일 다운로드 오류: {e}")
            return False
    
    def get_album_art(self, artist_name, album_name, release_date=None, download_dir="/tmp"):
        """
        앨범 아트 검색 및 다운로드
        
        Args:
            artist_name: 아티스트명
            album_name: 앨범명
            release_date: 발매일 (YYYY-MM-DD 또는 YYYY.MM.DD)
            download_dir: 다운로드 경로
        
        Returns:
            str: 다운로드된 파일 경로 또는 None
        """
        try:
            print(f"🔍 앨범 아트 검색: {artist_name} - {album_name}")
            if release_date:
                print(f"   발매일: {release_date}")
            
            # 1. 폴더 검색
            folder_id = self.search_folder(artist_name, album_name, release_date)
            if not folder_id:
                return None
            
            # 2. 앨범 아트 파일 찾기
            file_id, file_name = self.find_album_art(folder_id)
            if not file_id:
                return None
            
            # 3. 파일 다운로드
            # 안전한 파일명 생성
            safe_name = re.sub(r'[^\w\-_.]', '_', f"{artist_name}_{album_name}")
            ext = os.path.splitext(file_name)[1] or '.jpg'
            destination = os.path.join(download_dir, f"{safe_name}{ext}")
            
            if self.download_file(file_id, destination):
                return destination
            
            return None
            
        except Exception as e:
            print(f"❌ 앨범 아트 가져오기 오류: {e}")
            return None
    
    def list_folders(self, parent_folder_id=None, max_results=50):
        """폴더 목록 조회 (디버깅용)"""
        try:
            if parent_folder_id is None:
                parent_folder_id = self.ALBUM_ART_FOLDER_ID
            
            query = f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder'"
            
            # 공유 드라이브 지원
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
                pageSize=max_results,
                orderBy='name desc',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            
            folders = results.get('files', [])
            
            print(f"\n📁 폴더 목록 ({len(folders)}개):")
            for folder in folders[:20]:  # 최근 20개만 표시
                print(f"  - {folder['name']}")
            
            if len(folders) > 20:
                print(f"  ... 그 외 {len(folders) - 20}개")
            
            return folders
            
        except Exception as e:
            print(f"❌ 폴더 목록 조회 오류: {e}")
            return []


if __name__ == "__main__":
    # 테스트
    handler = DriveHandler("credentials/google_credentials.json")
    
    if handler.connect():
        # 폴더 목록 확인
        handler.list_folders()
        
        # 앨범 아트 검색 테스트
        path = handler.get_album_art("DIAN", "LOVE", "2026.02.16")
        print(f"다운로드 경로: {path}")

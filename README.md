# SeedM Releases — 자동 발매 페이지 (GitHub 무료 호스팅)

구글 시트(발매리스트) + 공유드라이브(앨범아트)를 읽어 발매 쇼케이스 페이지를 만들고,
**GitHub Actions가 매일 자동으로** 빌드·배포합니다. 맥/PC를 켜둘 필요 없습니다.

```
구글 시트(발매리스트) ─┐
                      ├─► GitHub Actions(매일) ─► website/ ─► GitHub Pages 공개 URL ─► 아임웹 iframe
구글 드라이브(앨범아트)─┘     (다운로드→빌드→업로드→이전 것 자동 정리)
```

- **앨범아트 라이프사이클**: 매 실행마다 그날 필요한 커버만 드라이브에서 새로 받아 올리고,
  배포 시 이전 사이트는 통째로 교체됩니다 → 오래된 커버는 **자동으로 사라짐**(따로 지울 것 없음).
- **비용**: Public 레포 + GitHub Pages + Actions = **전부 무료**.

---

## 처음 한 번만 하는 설정 (약 10분)

### 1. GitHub Desktop으로 레포 올리기
1. [GitHub Desktop](https://desktop.github.com/) 설치 후 본인 GitHub 계정으로 로그인.
2. **File → Add Local Repository** → 이 폴더(`seedm-site`) 선택.
   - "create a repository" 안내가 뜨면 클릭해서 생성.
3. 좌하단 **Publish repository** 클릭.
   - 이름: 예) `seedm-releases`
   - **"Keep this code private" 체크 해제** (Public이어야 Pages가 무료).
   - Publish.

> `.gitignore`가 키 파일·빌드산출물을 자동 제외하므로, 실수로 키가 올라갈 일은 없습니다.

### 2. 서비스계정 키를 Secret으로 등록 (Actions가 시트/드라이브 접근용)
1. 맥에서 `credentials/google_credentials.json` 파일을 텍스트 편집기로 열어 **내용 전체**를 복사.
2. GitHub 웹에서 방금 만든 레포 → **Settings → Secrets and variables → Actions → New repository secret**.
3. 입력:
   - **Name**: `GOOGLE_CREDENTIALS`
   - **Secret**: 복사한 JSON 전체 붙여넣기
4. Add secret.

> 이 서비스계정은 이미 발매리스트 시트 + 앨범아트 공유드라이브에 접근 권한이 있어야 합니다
> (맥에서 빌드가 되고 있었다면 이미 OK). 새 계정이라면 시트/드라이브를 그 계정 이메일에 공유하세요.

### 3. GitHub Pages 켜기
1. 레포 **Settings → Pages**.
2. **Source**를 `GitHub Actions`로 선택. (저장)

### 4. 첫 실행 + URL 확인
1. 레포 **Actions** 탭 → 왼쪽 `Build & Deploy SeedM Releases` → **Run workflow** 버튼.
2. 초록 체크가 뜨면 성공. 배포 URL은 보통:
   ```
   https://<본인계정>.github.io/seedm-releases/
   ```
   (Settings → Pages 상단에도 표시됨)

### 5. 아임웹에 연결
`EMBED_IMWEB.md` 참고. 아임웹 "코드입력/HTML" 위젯에 iframe 한 조각만 붙이고
`src`를 위 Pages URL로 바꾸면 끝. 이후 새 발매는 손 안 대도 매일 자동 반영됩니다.

---

## 자동 실행 주기
`.github/workflows/build.yml`의 cron — 한국시간 기준 **09:10 / 13:10 / 18:10** 하루 3회.
- 바꾸려면 `schedule` 의 cron(UTC) 수정. (한국시간 = UTC + 9시간)
- 언제든 Actions 탭에서 **Run workflow**로 수동 즉시 실행 가능.

## 로컬에서 테스트 (선택)
```powershell
pip install -r requirements.txt
# credentials/google_credentials.json 을 직접 두거나 환경변수로 경로 지정
python build.py
# → website/index.html, website/art/ 생성
```

## 설정값 위치 (`build.py` 상단)
| 항목 | 값 |
|------|-----|
| 스프레드시트 ID | `SPREADSHEET_ID` |
| 시트 이름 | `발매리스트` |
| 컬럼 | 아티스트 M / 앨범 N / 발매일 O / 곡명 AA |
| 앨범아트 드라이브 폴더 | `source/drive_handler.py` 의 `ALBUM_ART_FOLDER_ID` |

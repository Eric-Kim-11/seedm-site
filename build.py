"""
SeedM 릴리즈 페이지 빌드 (GitHub Actions / 로컬 공용).

흐름:
  1) 구글 시트(발매리스트)에서 오늘/어제/이번주 발매 수집 (취소선=발매취소 제외)
  2) 구글 공유드라이브에서 앨범아트 다운로드 → website/art/
  3) index.html 렌더 → website/index.html
  4) 이번 빌드에 안 쓰인 art/ 파일 자동 정리(삭제)

인증: 서비스계정 키.
  - GitHub Actions: 워크플로가 GOOGLE_CREDENTIALS 시크릿을 credentials/google_credentials.json 로 기록.
  - 로컬: 같은 경로에 키 파일을 두거나 GOOGLE_CREDENTIALS_FILE 환경변수로 경로 지정.

실행: `python build.py`  (Actions의 Ubuntu 러너에서도 동일하게 동작)
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))   # 한국 표준시 — 연도·날짜를 항상 한국 기준으로(서버 UTC 무관)

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE / "source"))

from release_page_v2 import render_index

# ── 설정 ─────────────────────────────────────────────────────────
CREDENTIALS = os.environ.get(
    "GOOGLE_CREDENTIALS_FILE", str(BASE / "credentials" / "google_credentials.json")
)
SPREADSHEET_ID = "1gcQUHfCeNBq0G3lzzNsckoe-SeP2rmsWHcee_0JbYHE"
SHEET_NAME = "발매리스트"
WEBSITE_DIR = BASE / "website"
ART_DIR = WEBSITE_DIR / "art"
COL_ARTIST, COL_ALBUM, COL_DATE, COL_TRACK = "M", "N", "O", "AA"
YT_CHANNEL_COL = None   # 발매리스트 자체에 채널열이 생기면 'XX'로 지정. 보통은 아래 백업탭 사용.

# 아티스트 유튜브 채널(프로필) 백업 — 아티스트DB 탭(접수페이지가 채우는 마스터)의 'G:유튜브뮤직' 열.
# A열=아티스트명, G열=유튜브 채널 URL. URL이 있으면 클릭 시 검색 대신 그 채널로 바로 연결.
ARTIST_DB_TAB = "아티스트DB"
ARTIST_DB_NAME_COL, ARTIST_DB_URL_COL = 0, 6   # A=아티스트명, G=유튜브뮤직(채널URL) (0-based)


def _norm(s):
    return (s or "").replace(" ", "").lower()


def _is_youtube(u):
    u = u.lower()
    return "youtube.com" in u or "youtu.be" in u


def load_artist_youtube(spreadsheet):
    """아티스트DB → {아티스트명: 유튜브채널URL}. exact·normalized 두 맵 반환(이름 표기 흔들림 대비).
    G열에 유튜브 아닌 링크(타 플랫폼 오입력)가 있으면 무시하고 경고 — 엉뚱한 사이트 연결 방지."""
    exact, norm = {}, {}
    bad = []
    try:
        rows = spreadsheet.worksheet(ARTIST_DB_TAB).get_all_values()
    except Exception as e:
        print(f"  아티스트DB 읽기 실패(무시): {e}")
        return exact, norm
    for r in rows[1:]:
        if len(r) <= ARTIST_DB_URL_COL:
            continue
        name = r[ARTIST_DB_NAME_COL].strip()
        url = r[ARTIST_DB_URL_COL].strip()
        if not (name and url.startswith("http")):
            continue
        if _is_youtube(url):
            exact.setdefault(name, url)
            norm.setdefault(_norm(name), url)
        else:
            bad.append((name, url))
    if bad:
        print(f"  ⚠ 아티스트DB G열에 유튜브 아닌 링크 {len(bad)}건 → 검색폴백 처리(고쳐주세요): "
              + ", ".join(f"{n}({u[:35]})" for n, u in bad[:8]))
    return exact, norm


def _col(letter):
    idx = 0
    for c in letter.upper():
        idx = idx * 26 + (ord(c) - ord('A') + 1)
    return idx - 1


def parse_date(s):
    s = (s or "").strip()[:10].replace(".", "-").replace("/", "-")
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return None


def get_releases(all_rows, strikethrough, start, end):
    """기간 [start, end) 발매곡. 취소선 제외, (아티스트,앨범) 중복 제거, 트랙명 수집."""
    a_i, b_i, d_i, t_i = _col(COL_ARTIST), _col(COL_ALBUM), _col(COL_DATE), _col(COL_TRACK)
    yt_i = _col(YT_CHANNEL_COL) if YT_CHANNEL_COL else None
    grouped = {}
    for row_num, row in enumerate(all_rows[1:], start=2):
        if row_num in strikethrough:
            continue
        if len(row) <= max(a_i, b_i, d_i):
            continue
        artist, album = row[a_i].strip(), row[b_i].strip()
        rd = parse_date(row[d_i].strip()) if len(row) > d_i else None
        if not (artist and album and rd):
            continue
        if not (start <= rd < end):
            continue
        key = (artist, album)
        track = row[t_i].strip() if len(row) > t_i else ""
        if key not in grouped:
            grouped[key] = {
                "artist": artist, "album": album,
                "release_date": rd.strftime("%Y-%m-%d"),
                "tracks": [],
                "yt_channel": (row[yt_i].strip() if yt_i is not None and len(row) > yt_i else None) or None,
            }
        if track and track not in grouped[key]["tracks"]:
            grouped[key]["tracks"].append(track)
    return list(grouped.values())


def _safe_name(r):
    return f"{r['artist']}_{r['album']}".replace("/", "_").replace(" ", "_")[:80]


def attach_album_art(drive, releases, keep: set):
    """각 발매곡 앨범커버를 Drive에서 받아 art/ 저장 → art_url 부여. keep에 사용 파일명 누적."""
    ART_DIR.mkdir(parents=True, exist_ok=True)
    for r in releases:
        safe = _safe_name(r)
        hit = None
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            p = ART_DIR / f"{safe}{ext}"
            if p.exists():
                hit = p
                break
        if not hit:
            try:
                tmp = drive.get_album_art(r["artist"], r["album"], r["release_date"], download_dir=str(ART_DIR))
                if tmp and Path(tmp).exists():
                    dest = ART_DIR / f"{safe}{Path(tmp).suffix.lower() or '.jpg'}"
                    if str(Path(tmp)) != str(dest):
                        Path(tmp).rename(dest)
                    hit = dest
            except Exception as e:
                print(f"  커버 실패 {r['artist']}-{r['album']}: {e}")
        if hit:
            keep.add(hit.name)
            r["art_url"] = f"art/{hit.name}"
        else:
            r["art_url"] = None
    return releases


def cleanup_art(keep: set):
    """이번 빌드에 안 쓰인 art/ 파일 삭제 (오래된 발매 커버 자동 정리)."""
    if not ART_DIR.exists():
        return 0
    removed = 0
    for p in ART_DIR.iterdir():
        if p.is_file() and p.name not in keep and p.name.lower() != "readme.txt":
            try:
                p.unlink()
                removed += 1
            except Exception as e:
                print(f"  정리 실패 {p.name}: {e}")
    if removed:
        print(f"🧹 사용 안 한 앨범아트 {removed}개 정리")
    return removed


def build():
    from sheet_handler import SheetHandler
    from drive_handler import DriveHandler

    now = datetime.now(KST)
    # 날짜 비교용은 naive로(시트 발매일도 naive). 표시용 now는 KST 그대로(연도·날짜 정확).
    today = now.replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)

    sh = SheetHandler(CREDENTIALS, SPREADSHEET_ID, SHEET_NAME)
    if not sh.connect():
        raise RuntimeError("구글 시트 연결 실패 — 서비스계정 키/공유 권한 확인")
    all_rows = sh.sheet.get_all_values()
    try:
        strikethrough = sh.get_strikethrough_rows()
    except Exception as e:
        print(f"취소선 조회 실패(무시): {e}")
        strikethrough = set()

    today_rel = get_releases(all_rows, strikethrough, today, today + timedelta(days=1))
    yest_rel = get_releases(all_rows, strikethrough, today - timedelta(days=1), today)
    week_rel = get_releases(all_rows, strikethrough, today - timedelta(days=7), today)

    # 아티스트 유튜브 채널 연결 (아티스트DB G열). 없으면 검색 폴백(render에서 처리).
    yt_exact, yt_norm = load_artist_youtube(sh.sheet.spreadsheet)
    for group in (today_rel, yest_rel, week_rel):
        for r in group:
            r["yt_channel"] = yt_exact.get(r["artist"]) or yt_norm.get(_norm(r["artist"]))
    seen, miss = set(), []
    for r in week_rel:
        if r["artist"] in seen:
            continue
        seen.add(r["artist"])
        if not r.get("yt_channel"):
            miss.append(r["artist"])
    print(f"🔗 유튜브 채널: 아티스트DB {len(yt_exact)}팀 로드 / "
          f"쇼케이스 {len(seen) - len(miss)}팀 연결, 미등록 {len(miss)}팀")
    if miss:
        print("   미등록(검색폴백) → 아티스트DB G열 채우면 직접연결: " + ", ".join(miss))

    drive = DriveHandler(CREDENTIALS)
    drive.connect()
    keep = set()
    for group in (today_rel, yest_rel, week_rel):
        attach_album_art(drive, group, keep)
    cleanup_art(keep)

    WEBSITE_DIR.mkdir(parents=True, exist_ok=True)
    html = render_index(today_rel, yest_rel, week_rel, now=now)
    (WEBSITE_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"🌐 빌드 완료 [{now:%Y-%m-%d %H:%M}] "
          f"오늘 {len(today_rel)} / 어제 {len(yest_rel)} / 이번주 {len(week_rel)}"
          f" → {WEBSITE_DIR / 'index.html'}")
    return {"today": len(today_rel), "yesterday": len(yest_rel), "week": len(week_rel)}


if __name__ == "__main__":
    build()

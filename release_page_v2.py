"""
SeedM 릴리즈 페이지 v2 — 렌더링 모듈 (web_developer_agent에 드롭인 가능).

추가 기능 (README TODO):
  1) 앨범아트 클릭 → YouTube Topic 채널 (채널URL 있으면 직접, 없으면 검색 폴백)
  2) 발매 예정(D-7) 섹션
  3) 카드 호버 시 트랙리스트 미리보기
  4) 모바일 반응형 강화

사용:
  - 맥 에이전트: 이 파일의 render_index/_render_card 등을 web_developer_agent.py에 이식.
    각 release dict에 선택 키 추가 가능: tracks(list[str]), yt_channel(url), art_url.
  - 프리뷰: `python release_page_v2.py` → preview.html 생성(샘플 데이터). 인증서 불필요.
"""
from urllib.parse import quote_plus
from datetime import datetime, timedelta
from pathlib import Path
from html import escape


def youtube_topic_url(artist: str, yt_channel: str | None = None) -> str:
    """YouTube Topic 채널 링크. 채널 URL 있으면 직접, 없으면 '아티스트 + topic' 검색 폴백."""
    if yt_channel:
        return yt_channel
    return f"https://www.youtube.com/results?search_query={quote_plus(artist + ' topic')}"


def _d_day_badge(release_date: str, today: datetime) -> str:
    """발매 예정 D-day 뱃지. 과거/오늘이면 빈 문자열."""
    try:
        rd = datetime.strptime(release_date, "%Y-%m-%d")
    except ValueError:
        return ""
    days = (rd.date() - today.date()).days
    if days <= 0:
        return ""
    label = "D-DAY" if days == 0 else f"D-{days}"
    return f'<span class="dday">{label}</span>'


def _render_card(r: dict, today: datetime, upcoming: bool = False) -> str:
    artist = escape(r["artist"])
    album = escape(r["album"])
    date = escape(r.get("release_date", ""))
    link = youtube_topic_url(r["artist"], r.get("yt_channel"))

    # 앨범아트
    if r.get("art_url"):
        art_inner = f'<img src="{escape(r["art_url"])}" alt="{album}" loading="lazy">'
    else:
        initial = (r["album"][:1] or r["artist"][:1] or "?").upper()
        art_inner = f'<div class="art-placeholder">{escape(initial)}</div>'

    # 호버 트랙리스트 미리보기
    tracks = r.get("tracks") or []
    if tracks:
        items = "".join(f"<li>{escape(t)}</li>" for t in tracks[:8])
        more = f'<li class="more">+{len(tracks) - 8}곡</li>' if len(tracks) > 8 else ""
        track_overlay = f'<div class="tracklist"><ol>{items}{more}</ol></div>'
        track_chip = f'<span class="track-count">{len(tracks)}곡</span>'
    else:
        track_overlay = ""
        track_chip = ""

    dday = _d_day_badge(date, today) if upcoming else ""

    return f"""<a class="card" href="{link}" target="_blank" rel="noopener" title="{artist} · YouTube Topic">
  <div class="art">{art_inner}{track_overlay}{dday}</div>
  <div class="meta">
    <div class="album">{album}</div>
    <div class="artist">{artist}</div>
    <div class="date">{date} {track_chip}</div>
  </div>
</a>"""


def _render_section(title: str, releases: list[dict], today: datetime, upcoming: bool = False) -> str:
    # 발매가 없는 섹션은 통째로 숨김 (빈 섹션 미노출)
    if not releases:
        return ""
    cards = "\n".join(_render_card(r, today, upcoming) for r in releases)
    return f"""<section class="section">
  <header class="section-head"><h2>{escape(title)}</h2><span class="count">{len(releases)}</span></header>
  <div class="grid">{cards}</div>
</section>"""


def render_index(today_releases, yesterday_releases, week_releases, upcoming_releases=None,
                 now=None, auto_refresh_sec: int = 1800) -> str:
    now = now or datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # 발매예정(D-7) 섹션은 사용 안 함 (eric 정책 2026-06-02) — upcoming_releases는 무시
    # 순서: 오늘(상단) → 어제(중단) → 이번주(하단). 빈 섹션은 자동 숨김(_render_section이 "" 반환).
    sections = (
        _render_section("Today", today_releases, today)
        + _render_section("Yesterday", yesterday_releases, today)
        + _render_section("This Week", week_releases, today)
    )
    if not sections.strip():
        sections = '<div class="empty">No recent releases.</div>'
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{auto_refresh_sec}">
<title>SeedM — New Releases</title>
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
@import url('https://fonts.googleapis.com/css2?family=Montserrat:ital,wght@0,400..800;1,400..700&display=swap');
/* ── 색 테마 (seedm.net 홈페이지 톤에 맞춤) ──
   배경 톤만 바꾸려면 아래 --bg 한 줄만 수정하면 전체가 따라옵니다. */
:root{{
  --bg:#111111;      /* 페이지 배경 — 홈페이지 배경색과 동일 */
  --fg:#f5f5f5;      /* 기본 글자 */
  --muted:#8a8a8a;   /* 보조 글자(아티스트·날짜·카운트) */
  --card:#1c1c1c;    /* 앨범아트 빈자리 배경 */
  --border:#262626;  /* 구분선 */
  --chip:#222222;    /* 트랙수 칩 배경 */
  --accent:#00b8ff;  /* 포인트색 — 홈페이지 시안 */
}}
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{background:var(--bg);color:var(--fg);font-family:'Montserrat','Pretendard Variable',-apple-system,sans-serif;}}
body{{min-height:100vh;padding:64px 24px 80px;}}
main{{max-width:1400px;margin:0 auto;}}
.hero{{margin-bottom:56px;display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid var(--border);padding-bottom:18px;}}
.hero h1{{font-size:24px;font-weight:800;letter-spacing:1.5px;}}
.hero .date{{font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums;}}
.section{{margin-bottom:56px;}}
.section:last-child{{margin-bottom:0;}}
.section-head{{display:flex;align-items:baseline;gap:10px;margin-bottom:24px;}}
.section-head h2{{font-size:16px;font-weight:700;letter-spacing:1px;text-transform:uppercase;}}
.section-head .count{{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:28px 18px;}}
.card{{display:block;text-decoration:none;color:inherit;}}
.art{{position:relative;aspect-ratio:1;background:var(--card);border-radius:6px;overflow:hidden;}}
.art img{{width:100%;height:100%;object-fit:cover;display:block;transition:transform .4s ease;}}
.card:hover .art img{{transform:scale(1.04);}}
.art-placeholder{{width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:56px;font-weight:200;color:#333;}}
/* 호버 트랙리스트 */
.tracklist{{position:absolute;inset:0;background:rgba(0,0,0,.82);color:#fff;opacity:0;transition:opacity .25s ease;
  display:flex;align-items:center;padding:18px;pointer-events:none;backdrop-filter:blur(2px);}}
.card:hover .tracklist{{opacity:1;}}
.tracklist ol{{list-style:decimal inside;font-size:12px;line-height:1.9;max-height:100%;overflow:hidden;}}
.tracklist .more{{list-style:none;color:var(--accent);margin-top:4px;}}
/* D-day 뱃지 */
.dday{{position:absolute;top:10px;left:10px;background:var(--accent);color:#001a24;font-size:11px;font-weight:800;
  padding:3px 8px;border-radius:6px;letter-spacing:.3px;}}
.meta{{padding:11px 2px 0;}}
.album{{font-size:14px;font-weight:600;margin-bottom:3px;letter-spacing:-0.3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.artist{{font-size:12px;color:var(--muted);margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.date{{font-size:10px;color:var(--muted);letter-spacing:.5px;font-variant-numeric:tabular-nums;display:flex;align-items:center;gap:6px;}}
.track-count{{background:var(--chip);color:var(--muted);padding:1px 6px;border-radius:4px;font-size:10px;}}
.empty{{grid-column:1/-1;padding:32px 0;color:#444;font-size:13px;}}
footer{{margin-top:72px;border-top:1px solid var(--border);padding-top:18px;font-size:11px;color:var(--muted);letter-spacing:.5px;}}
/* 모바일 반응형 */
@media (max-width:640px){{
  body{{padding:40px 16px 56px;}}
  .grid{{grid-template-columns:repeat(2,1fr);gap:20px 12px;}}
  .hero{{margin-bottom:36px;flex-direction:column;gap:4px;}}
  .hero h1{{font-size:20px;}}
  .section{{margin-bottom:40px;}}
  /* 터치기기: 호버 불가 → 탭 시 트랙리스트 노출 */
  .card:active .tracklist{{opacity:1;}}
}}
@media (hover:none){{ .track-count{{display:inline-block;}} }}
</style>
</head>
<body>
<main>
  <div class="hero"><h1>NEW RELEASES</h1><div class="date">{now.strftime('%Y.%m.%d')}</div></div>
  {sections}
  <footer>© {now.year} SeedM Inc. All rights reserved.</footer>
</main>
<script>
/* 아임웹 등 부모 페이지 iframe 높이 자동조정용: 본문 높이를 부모로 전달 */
(function(){{
  function postH(){{ try{{ parent.postMessage({{seedmHeight: document.body.scrollHeight}}, '*'); }}catch(e){{}} }}
  window.addEventListener('load', postH);
  window.addEventListener('resize', postH);
  setInterval(postH, 1500);
}})();
</script>
</body>
</html>"""


# ── 프리뷰용 샘플 데이터 + 실행 ──
if __name__ == "__main__":
    now = datetime(2026, 6, 2, 12, 10)
    def d(offset): return (now + timedelta(days=offset)).strftime("%Y-%m-%d")
    today_rel = [
        {"artist": "DIAN", "album": "LOVE", "release_date": d(0),
         "tracks": ["LOVE", "LOVE (Inst.)"]},
        {"artist": "우예린", "album": "Midnight Blue", "release_date": d(0),
         "tracks": ["Midnight Blue", "Rainy Window", "Last Train", "Blue (Inst.)"]},
    ]
    upcoming_rel = [
        {"artist": "SeedM Jazz", "album": "Late Night Sessions", "release_date": d(3),
         "tracks": ["Smoke & Keys", "3 A.M. Walk", "Velvet Room"]},
        {"artist": "한지수", "album": "여름의 끝", "release_date": d(6), "tracks": ["여름의 끝"]},
    ]
    yesterday_rel = [
        {"artist": "Moody Trio", "album": "Blue Note Diary", "release_date": d(-1),
         "tracks": ["Intro", "Diary", "Coffee Break", "Outro", "Diary (Live)"]},
    ]
    week_rel = today_rel + yesterday_rel + [
        {"artist": "노을", "album": "Sunset", "release_date": d(-4), "tracks": ["Sunset", "Afterglow"]},
    ]
    html = render_index(today_rel, yesterday_rel, week_rel, upcoming_rel, now=now)
    out = Path(__file__).parent / "preview.html"
    out.write_text(html, encoding="utf-8")
    print(f"프리뷰 생성: {out}")
    print("브라우저로 열어 확인하세요. (오늘2/예정2/어제1/이번주4 샘플)")

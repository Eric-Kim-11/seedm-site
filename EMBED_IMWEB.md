# 아임웹(Imweb)에 SeedM 릴리즈 페이지 임베드 + 자동 업데이트

## 핵심: "자동 리프레시"는 두 개의 층

```
[1. 데이터 자동갱신 — 백엔드]            [2. 화면 자동새로고침 — 프론트]
맥에서 build_index.py가 매일 실행          방문자 브라우저가 주기적으로 새로고침
→ index.html + art/ 새로 생성·배포    →   → meta refresh(기본 30분)로 새 데이터 표시
```
둘 다 이미 준비됨: 백엔드는 `--watch`/cron, 프론트는 페이지에 `<meta http-equiv="refresh">` 내장.

---

## 왜 "코드만 붙여넣기"는 iframe이어야 하나

아임웹 코드블록에 HTML을 **그대로 붙여넣으면 그 순간의 데이터로 고정**됩니다(자동갱신 X). 자동으로 새 발매가 반영되게 하려면, **외부에 호스팅된 페이지를 iframe으로 불러오는** 방식이어야 합니다. 그러면 호스팅된 파일만 매일 갱신되면 아임웹은 손 안 대도 최신이 됩니다.

```
호스팅서버(index.html+art/)  ←매일 갱신←  맥 build_index.py
        ↑ iframe src
아임웹 페이지 (코드블록에 iframe 한 조각만)
```

---

## 1단계: 호스팅 (index.html + art/ 를 공개 URL로)

`build_index.py`가 만드는 건 **폴더**(index.html + art/이미지)라 어딘가에 공개 호스팅 필요. 옵션:

| 방법 | 비용 | 난이도 | 비고 |
|------|------|--------|------|
| **Netlify Drop** | 무료 | ★ 쉬움 | website 폴더 드래그&드롭 → 즉시 URL. CLI로 자동배포도 가능 |
| **GitHub Pages** | 무료 | ★★ | 레포에 push → username.github.io/... |
| **Cloudflare Pages** | 무료 | ★★ | 깃 연동 자동배포 |
| 자체 서버/도메인 | - | ★★ | 회사 서버 있으면 website/ 업로드 |

> 아임웹 자체 파일호스팅은 폴더형 정적사이트엔 부적합 → 위 정적호스팅 권장.

**자동배포(매일):** 맥 cron/launchd에서 `build_index.py` 실행 후 배포 명령까지 한번에. 예(Netlify CLI):
```bash
python build_index.py && netlify deploy --dir=website --prod
```
(GitHub Pages면 `git add -A && git commit -m auto && git push`)

---

## 2단계: 아임웹에 iframe 코드 삽입

아임웹 편집 → 원하는 위치에 **"코드입력/HTML" 위젯** 추가 → 아래 붙여넣기 (URL만 본인 호스팅 주소로):

```html
<iframe id="seedm-releases"
        src="https://YOUR_HOST/index.html"
        style="width:100%;border:0;display:block;min-height:600px;"
        scrolling="no"></iframe>
<script>
/* 페이지(iframe)가 보내는 높이로 자동 맞춤 → 내부 스크롤바 없이 자연스럽게 */
window.addEventListener('message', function(e){
  if (e.data && e.data.seedmHeight) {
    document.getElementById('seedm-releases').style.height = e.data.seedmHeight + 'px';
  }
});
</script>
```

- `src`만 본인 호스팅 URL로 바꾸면 끝.
- 높이 자동조정 스크립트는 페이지에 내장된 `postMessage(seedmHeight)`와 짝 → 발매곡 수가 늘어도 잘림/스크롤 없이 딱 맞게 늘어남.
- 페이지 자체가 30분마다 새로고침(meta refresh)되므로 방문자가 머물러도 새 발매가 반영됨. (간격 조정: render_index의 `auto_refresh_sec`)

---

## (대안) 자동갱신 필요 없이 "지금 모습 그대로" 한 번만 붙일 때

자동갱신이 필요 없다면 iframe 대신 `<style>`+`<main>` 영역만 코드블록에 붙여도 됩니다. 단 이 경우 **새 발매 반영 시 매번 다시 붙여넣어야** 합니다(비추천).

---

## 점검 체크리스트
- [ ] 맥에서 `build_index.py` 정상 빌드(커버 다운로드 포함)
- [ ] website 폴더(호스트) 공개 URL 접속 확인 (index.html + art/이미지 함께)
- [ ] cron/launchd로 매일 빌드+배포 자동화
- [ ] 아임웹 코드블록에 iframe 삽입, src 교체
- [ ] 모바일/PC에서 높이 자동조정·새로고침 확인

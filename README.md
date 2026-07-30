# 포트폴리오 데일리 브리핑 — GitHub Actions 자동화

**PC를 꺼둬도** 매일 아침 7시(KST)에 브리핑이 생성돼 카카오톡으로 옵니다.

```
GitHub Actions (클라우드)
  ├ 1. 시세 수집    stockanalysis.com API + 거래일 검증  ← 실패 시 여기서 중단
  ├ 2. 뉴스 수집    Brave Search API
  ├ 3. 브리핑 생성  Claude API
  ├ 4. 발행        GitHub Pages (영구 보존, 만료 없음)
  └ 5. 발송        카카오톡 '나에게 보내기' API (200자 + 링크)
```

---

## 왜 이 구조인가

| 기존 (Cowork 예약) | 이 구조 |
|---|---|
| PC가 켜져 있어야 함 | **클라우드에서 실행** |
| Send 링크 24시간 만료 | **GitHub Pages 영구 보존 + 아카이브** |
| 커넥터 도구명이 재연결 시 변경 | 공식 API 직접 호출 |
| 비용 없음 | **월 약 $5~12** (아래 참고) |

---

## 설치 (한 번만, 약 30분)

### 1단계 — 레포 만들기

```bash
gh repo create portfolio-briefing --private --clone
cd portfolio-briefing
# 이 폴더의 파일들을 복사해 넣고
git add . && git commit -m "init" && git push
```

> **Private 레포 주의:** GitHub Pages를 쓰려면 Public이거나 유료 플랜이 필요합니다.
> Private으로 하려면 Pages 대신 브리핑을 카톡 여러 통으로 나눠 보내야 합니다.
> **Public으로 하되 레포에 개인정보를 넣지 않는 방식을 권장합니다** (보유 수량 등은 절대 커밋 금지).

### 2단계 — GitHub Pages 켜기

Settings → Pages → Source: `Deploy from a branch` → Branch: `main` / 폴더: `/docs` → Save

몇 분 뒤 `https://<아이디>.github.io/portfolio-briefing/` 이 살아납니다.

### 3단계 — 카카오 개발자 앱 만들기

[developers.kakao.com](https://developers.kakao.com) 에서:

1. **애플리케이션 추가하기**
2. 앱 설정 → 앱 키 → **REST API 키** 복사
3. 카카오 로그인 → **활성화 ON**
4. 카카오 로그인 → Redirect URI 등록: `http://localhost:8080/callback`
5. 카카오 로그인 → 동의항목 → **카카오톡 메시지 전송(talk_message)** 을 `이용 중 동의`로 설정

> ✅ **'나에게 보내기'는 비즈앱 전환이나 별도 사용 권한 신청이 필요 없습니다.**
> (공식 문서 확인 — 친구에게 보내기만 권한 신청 대상입니다)

그다음 **내 PC에서 한 번만** 실행해 리프레시 토큰을 받습니다:

```bash
pip install requests
python scripts/get_kakao_token.py
```

브라우저가 열리고 로그인·동의하면 터미널에 토큰이 출력됩니다.

### 4단계 — 시크릿 등록

Settings → Secrets and variables → Actions → **New repository secret**

| 이름 | 값 | 필수 |
|---|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) 에서 발급 | ✅ |
| `KAKAO_REST_API_KEY` | 3단계에서 복사한 REST API 키 | ✅ |
| `KAKAO_REFRESH_TOKEN` | 3단계 스크립트 출력값 | ✅ |
| `BRAVE_API_KEY` | [brave.com/search/api](https://brave.com/search/api/) 무료 티어 | 권장 |
| `GH_PAT` | `repo` 권한 PAT — 리프레시 토큰 자동 갱신용 | 선택 |

**Variables** 탭에 (선택):

| 이름 | 값 |
|---|---|
| `PAGES_BASE` | `https://<아이디>.github.io/portfolio-briefing` |

### 5단계 — 수동 실행으로 테스트

Actions → `Daily Portfolio Briefing` → **Run workflow**

---

## 비용

| 항목 | 월 비용 |
|---|---|
| GitHub Actions | **무료** (Public 무제한 / Private 2,000분, 이 작업은 월 약 60분) |
| GitHub Pages | **무료** (Public) |
| 카카오 API | **무료** ('나에게 보내기'는 쿼터 제한 없음) |
| Brave Search | **무료** (월 2,000쿼리, 이 작업은 월 약 300쿼리) |
| Claude API | **약 $5~12** ← 유일한 유료 항목 |

Claude API 추정: 1회당 입력 약 60K + 출력 약 15K 토큰.
Sonnet 5 기준 $2/$10 per 1M (2026년 8월 31일까지 프로모션, 이후 $3/$15) →
1회 약 $0.27, 월 22회 약 **$6**. Haiku로 바꾸면 절반 이하지만 브리핑 품질이 떨어집니다.

`CLAUDE_MODEL` 환경변수로 모델을 바꿀 수 있습니다.

---

## 알아둘 제약

**GitHub Actions 예약 실행은 정시성이 보장되지 않습니다.**
공식적으로 지연될 수 있고, 실제로 **5~30분 지연**이 흔합니다. 부하가 심하면 드물게 스킵됩니다.
정확히 7시에 받고 싶으면 cron을 `40 21 * * 0-4`(KST 06:40)로 당겨두세요.

**60일 무활동 시 예약 워크플로가 자동 비활성화됩니다.**
예약 실행 성공은 '활동'으로 치지 않습니다. `keepalive.yml`이 매주 빈 커밋을 남겨 이를 방지합니다.
다만 브리핑 워크플로 자체가 매일 `docs/`에 커밋하므로 실질적으로는 이중 안전장치입니다.

**카카오 리프레시 토큰은 약 2개월입니다.**
만료 1개월 미만이 되면 갱신 시 새 토큰이 함께 내려옵니다.
`GH_PAT`를 등록해두면 시크릿이 자동 교체되고, 없으면 로그에 새 토큰이 출력되니 수동 교체하면 됩니다.

**미국 증시 휴장일은 매년 갱신해야 합니다.**
`scripts/fetch_quotes.py`의 `HOLIDAYS_2026`을 연말에 다음 해 것으로 바꿔주세요.
빠뜨리면 휴장일 다음 날 거래일 검증이 실패하며 발송이 중단됩니다(틀린 데이터가 나가는 것보다 안전).

**서머타임**
cron은 UTC 고정이라 미국 서머타임이 끝나면 미국 장 시간이 1시간 밀립니다.
한국 시간 기준 발송 시각은 그대로 07:00이고 전날 종가를 다루므로 실무상 영향은 없습니다.

---

## 설계 원칙 — 왜 검증 게이트를 뒀나

이 프로젝트에는 **틀린 데이터를 자신있게 보내지 않는다**는 원칙이 박혀 있습니다.
실제로 캐시된 2거래일 지난 시세를 최신으로 착각해 보고한 적이 있었고,
그때 낙폭이 실제보다 최대 9.5%p 작게 표시됐습니다.

그래서:

- 캐시버스터는 **매 호출 무작위**. 날짜 기반 고정값 금지 (그게 원인이었음)
- 응답의 `td` 필드를 계산된 예상 거래일과 **대조**
- 한 종목이라도 불일치하면 **워크플로 전체 실패** — 발송하지 않음
- 실패 시 조용히 넘어가지 않고 카톡으로 실패 알림 발송

느슨하게 넘어가는 것보다 안 보내는 편이 낫다는 판단입니다.

---

## 파일 구조

```
.github/workflows/
  briefing.yml        메인 워크플로 (KST 평일 07:00)
  keepalive.yml       60일 비활성화 방지
scripts/
  fetch_quotes.py     시세 + 거래일 검증 (검증 게이트)
  fetch_news.py       Brave Search
  build_briefing.py   Claude API — HTML + 카톡 200자 동시 생성
  publish.py          GitHub Pages 발행 + 아카이브
  kakao_send.py       토큰 갱신 + 나에게 보내기
  get_kakao_token.py  [최초 1회] 내 PC에서 실행
docs/                 발행된 브리핑 (자동 생성)
data/                 실행 중 임시 파일 (gitignore)
```

---

*본 도구가 만드는 문서는 정보 제공 목적이며 투자 자문이 아닙니다.*

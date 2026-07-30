"""
3단계 — 브리핑 생성 (Claude API)

시세 JSON + 뉴스 JSON을 넣고, HTML 본문과 카톡 200자 요약을 함께 받는다.
출력은 data/briefing.json  { "html": ..., "kakao": ..., "headline": ... }
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

KST = ZoneInfo("Asia/Seoul")
DATA = Path("data")
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")

quotes = json.loads((DATA / "quotes.json").read_text(encoding="utf-8"))
news = json.loads((DATA / "news.json").read_text(encoding="utf-8"))
now_kst = datetime.now(KST)

SYSTEM = """\
너는 한국 개인투자자를 위한 미국주식 데일리 브리핑을 쓴다. 모든 출력은 한국어다.
영문 뉴스는 반드시 한국어로 번역해서 정리한다. 원문을 그대로 붙이지 않는다.

## 절대 규칙
1. **주어진 시세 데이터만 사용한다.** 기억에 의존해 가격을 지어내지 않는다.
   숫자는 입력 JSON의 값을 그대로 쓴다.
2. **뉴스는 확인된 날짜를 명시한다.** 날짜를 알 수 없으면 "날짜 미확인"으로 표기하고
   절대 당일자로 위장하지 않는다. 검색 결과에 없는 사실을 만들어내지 않는다.
3. **투자자문 금지.** 매수/매도를 지시하지 않는다. "재무 상담사가 아니다"를 명시한다.
   무엇을 하라가 아니라, 데이터가 무엇을 말하는지와 어떤 질문에 미리 답을 준비하면
   판단이 쉬워지는지를 제시한다. 리스크 집중·레버리지 감쇠 같은 구조적 사실은
   관찰로서 짚어준다.
4. 확실하지 않으면 확실하지 않다고 쓴다. 틀린 내용을 자신있게 쓰는 것이 최악이다.

## 종목 혼동 주의
- ORCX는 개별주가 아니라 오라클(ORCL) 2배 레버리지 ETF다. 뉴스는 ORCL 기준으로 해석하되
  ORCX 자체의 레버리지 감쇠도 언급한다.
- INFQ는 Infleqtion(양자컴퓨팅 기업)이다. 2배 ETF인 INFH와 다르다.
- TQQQ(3배)와 QLD(2배)는 같은 나스닥100 지수의 중복 포지션이다. 분산이 아니다.

## 사용자 선호
간결하고 직설적으로. 군더더기 배제. 표를 적극 활용. 데이터 정확성을 최우선으로 여김.

## 출력 형식
아래 두 블록을 정확히 이 마커로 감싸서 출력한다. 마커 밖에는 아무것도 쓰지 않는다.

===HTML===
(완전한 자체 포함 HTML 문서. <!DOCTYPE html>로 시작)
===/HTML===

===KAKAO===
(카카오톡 본문. URL이 들어갈 자리에 정확히 {{URL}} 이라고 쓴다.
 {{URL}}을 30자로 계산했을 때 전체가 200자 이하여야 한다.
 즉 {{URL}}을 제외한 본문은 165자 이내.)
===/KAKAO===

## HTML 요구사항
- 외부 의존성 0. 인라인 CSS/JS만. 이미지 없음.
- 모바일 퍼스트(휴대폰에서 링크로 열어 읽음). word-break:keep-all 로 한글 줄바꿈 처리.
- prefers-color-scheme: dark 지원 (CSS 변수 사용).
- 표는 좁은 화면에서 세로 카드로 전환. 가로 스크롤보다 읽기 편하게.
- 폰트: -apple-system, "Apple SD Gothic Neo", "Malgun Gothic" + 숫자/티커는 모노.
- 의미 색상 고정: 빨강=하락/리스크노출, 초록=상승/저상관방어, 앰버=주의신호. 문서 전체 일관.
- 종목 상세는 <details>로 접어 스크롤 길이를 관리한다.
- 스크롤 진입 시 바 성장 애니메이션(IntersectionObserver 1개) 정도만. 과한 모션 금지.

## 문서 구성
1. 헤더 — 작성 시각(KST) + 대상 거래일 + 날짜 검증 완료 배지
2. 한 줄 요약 — 어제 장을 움직인 핵심 원인과 포트폴리오 영향
3. 종가 — 10종목. 등락률 비율대로 바를 그려 낙폭 격차가 눈에 보이게
4. 시장을 움직인 결정적 사건 3가지 — 각각 "왜 중요한가" 포함
5. 오늘 밤 변수 — 상승 재료 vs 하락 재료 대비
6. 종목별 카드 10개 — 크리티컬 뉴스 + 방향성 판단 포인트. 반대편 근거도 함께
7. 리스크 구조 — 어느 리스크 축에 몇 종목이 몰렸는지. 레버리지 상품 명시
8. ★ 오늘의 전략 코멘트 (사용자가 가장 중요하게 여기는 섹션)
   - 핵심 조언 1개 (데이터 근거 필수)
   - 무시하면 안 되는 신호 2~3개 (CDS·금리·수급 등 주가 선행 지표 중심)
   - 오늘 취할 액션 (시간대별. 확인·준비·계산 항목으로)
9. 체크리스트 + 다가오는 일정 (미 장 개장 KST 22:30, 서머타임 종료 시 23:30)
10. 데이터 검증 기록 — 거래일 검증 결과, 미확인 항목 명시

## 카톡 요약 구성 (우선순위 순)
1. 날짜 + 기준 거래일  2. 한 줄 원인  3. 낙폭/상승 상위 3종목 등락률
4. 당일 최대 변수  5. {{URL}}
"""


def main() -> int:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print("ANTHROPIC_API_KEY 없음", file=sys.stderr)
        return 1

    client = anthropic.Anthropic(api_key=key)

    user = f"""\
현재 시각(KST): {now_kst:%Y-%m-%d (%a) %H:%M}
대상 거래일: {quotes['session_label_kr']}
거래일 검증: 전 종목 td 필드 = {quotes['session_date']} 확인 완료

## 시세 데이터 (이 숫자만 사용할 것)
{json.dumps(quotes['quotes'], ensure_ascii=False, indent=2)}

## 뉴스 검색 결과 (뉴스 사용 가능: {news.get('available')})
{json.dumps(news.get('items', []), ensure_ascii=False, indent=2)[:60000]}

위 자료로 오늘의 브리핑을 작성해줘."""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=32000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")

    html_m = re.search(r"===HTML===\s*(.*?)\s*===/HTML===", text, re.S)
    kakao_m = re.search(r"===KAKAO===\s*(.*?)\s*===/KAKAO===", text, re.S)
    if not html_m or not kakao_m:
        print("출력 파싱 실패. 원본 앞부분:\n" + text[:2000], file=sys.stderr)
        return 1

    html = html_m.group(1).strip()
    kakao = kakao_m.group(1).strip()

    # 200자 검증 — URL을 30자로 가정
    projected = len(kakao.replace("{{URL}}", "x" * 30))
    print(f"카톡 예상 길이: {projected}자")
    if projected > 200:
        # 뒤에서부터 줄 단위로 잘라 200자 이하로 맞춘다 (URL 줄은 보존)
        lines = kakao.split("\n")
        while lines and len("\n".join(lines).replace("{{URL}}", "x" * 30)) > 200:
            for i in range(len(lines) - 1, -1, -1):
                if "{{URL}}" not in lines[i]:
                    lines.pop(i)
                    break
            else:
                break
        kakao = "\n".join(lines)
        print(f"  → 축약 후: {len(kakao.replace('{{URL}}', 'x'*30))}자")

    (DATA / "briefing.json").write_text(
        json.dumps({"html": html, "kakao": kakao,
                    "session_date": quotes["session_date"]},
                   ensure_ascii=False),
        encoding="utf-8",
    )
    u = resp.usage
    print(f"✅ 생성 완료 (input {u.input_tokens:,} / output {u.output_tokens:,} 토큰)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

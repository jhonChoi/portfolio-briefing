"""
1단계 — 시세 수집 + 거래일 검증

핵심 원칙: 받아온 데이터의 날짜를 반드시 검증한다.
예상 거래일과 다르면 조용히 넘어가지 않고 실패시킨다.
(과거에 캐시된 2거래일 지난 시세를 최신으로 착각해 보고한 실수가 있었음)
"""
from __future__ import annotations

import json
import secrets
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

NY = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")
OUT = Path("data"); OUT.mkdir(exist_ok=True)

TICKERS = ["TQQQ", "QLD", "NVDA", "BMNR", "MSTR", "CRCL", "INFQ", "ABCL", "ORCX", "ARKX"]

# 종목 성격 — 브리핑 생성 시 혼동 방지용으로 함께 전달
PROFILE = {
    "TQQQ": "나스닥100 3배 레버리지 ETF",
    "QLD":  "나스닥100 2배 레버리지 ETF (TQQQ와 동일 지수, 중복 포지션)",
    "NVDA": "엔비디아",
    "BMNR": "BitMine Immersion — 이더리움 트레저리 기업",
    "MSTR": "Strategy (구 MicroStrategy) — 비트코인 트레저리 기업",
    "CRCL": "Circle Internet Group — USDC 스테이블코인 발행사",
    "INFQ": "Infleqtion — 중성원자 양자컴퓨팅 기업(NYSE). 2배 ETF인 INFH와 다름",
    "ABCL": "AbCellera Biologics — 항체 발굴 바이오",
    "ORCX": "Defiance Daily Target 2X Long ORCL ETF — 오라클 2배 레버리지 ETF (개별주 아님)",
    "ARKX": "ARK 우주·방산 혁신 ETF",
}

# 미국 증시 휴장일 (매년 갱신 필요)
HOLIDAYS_2026 = {
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
}


def expected_session_date(now_ny: datetime) -> str:
    """가장 최근에 종료된 미국 정규장 거래일 (YYYY-MM-DD)"""
    d = now_ny.date()
    if now_ny.hour < 16:          # 아직 오늘 종가 미확정
        d -= timedelta(days=1)
    for _ in range(10):
        if d.weekday() < 5 and d.isoformat() not in HOLIDAYS_2026:
            return d.isoformat()
        d -= timedelta(days=1)
    raise RuntimeError("거래일 계산 실패")


def fetch(ticker: str) -> dict:
    """캐시버스터는 매 호출마다 무작위 — 고정값은 과거 실수의 직접 원인"""
    last_err = None
    for attempt in range(3):
        cb = secrets.token_hex(6)
        url = f"https://stockanalysis.com/api/quotes/s/{ticker}?cb={cb}"
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            payload = r.json()
            if payload.get("status") == 200 and payload.get("data"):
                return payload["data"]
            last_err = f"unexpected payload: {payload}"
        except Exception as e:                      # noqa: BLE001
            last_err = repr(e)
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{ticker} 조회 실패: {last_err}")


def main() -> int:
    now_ny = datetime.now(NY)
    now_kst = datetime.now(KST)
    expected = expected_session_date(now_ny)

    print(f"실행(KST) : {now_kst:%Y-%m-%d %H:%M}")
    print(f"실행(ET)  : {now_ny:%Y-%m-%d %H:%M}")
    print(f"예상 거래일: {expected}\n")

    rows, stale = [], []
    for t in TICKERS:
        d = fetch(t)
        td = d.get("td")
        ok = (td == expected)
        if not ok:
            stale.append((t, td))
        rows.append({
            "ticker": t,
            "profile": PROFILE[t],
            "date": td,
            "date_ok": ok,
            "close": d.get("p"),
            "change": d.get("c"),
            "change_pct": d.get("cp"),
            "prev_close": d.get("cl"),
            "open": d.get("o"), "high": d.get("h"), "low": d.get("l"),
            "volume": d.get("v"),
            "after_hours": d.get("ep"),
            "after_hours_pct": d.get("ecp"),
            "high_52w": d.get("h52"), "low_52w": d.get("l52"),
            "exchange": d.get("ex"),
        })
        flag = "OK " if ok else "STALE"
        print(f"  {flag} {t:<5} {d.get('p'):>9}  {d.get('cp'):>7}%  ({td})")

    # ── 검증 게이트 ────────────────────────────────────────────
    # 틀린 데이터를 보내느니 아무것도 안 보내는 게 낫다
    if stale:
        print("\n❌ 거래일 불일치 — 발송 중단", file=sys.stderr)
        for t, td in stale:
            print(f"   {t}: 받은 값 {td} / 기대값 {expected}", file=sys.stderr)
        return 1

    payload = {
        "generated_at_kst": now_kst.isoformat(),
        "session_date": expected,
        "session_label_kr": f"미국 {expected} 정규장 종가",
        "verified": True,
        "quotes": rows,
    }
    (OUT / "quotes.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n✅ 전 {len(rows)}종목 거래일 검증 통과 → data/quotes.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
2단계 — 뉴스 수집 (Brave Search API)

Brave는 무료 티어 월 2,000쿼리. 이 작업은 하루 약 14쿼리 → 월 300쿼리로 충분.
BRAVE_API_KEY가 없으면 뉴스 없이 진행한다 (시세만으로도 브리핑은 성립).
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

KST = ZoneInfo("Asia/Seoul")
OUT = Path("data"); OUT.mkdir(exist_ok=True)
KEY = os.environ.get("BRAVE_API_KEY", "").strip()
ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

quotes = json.loads((OUT / "quotes.json").read_text(encoding="utf-8"))
session = quotes["session_date"]                      # YYYY-MM-DD
d = datetime.fromisoformat(session)
md = f"{d.month}월 {d.day}일"

# 주가 방향성에 영향을 주는 크리티컬 뉴스 중심으로 쿼리 구성
QUERIES = [
    f"stock market close {session} Fed treasury yield Nasdaq S&P",
    f"big tech earnings after hours reaction {session}",
    f"Nvidia NVDA news {session} AI capex",
    f"MicroStrategy MSTR bitcoin treasury news {session}",
    f"BitMine BMNR ethereum treasury news {session}",
    f"Circle CRCL stablecoin news analyst {session}",
    f"Infleqtion INFQ quantum stock news {session}",
    f"AbCellera ABCL news partnership {session}",
    f"Oracle ORCL stock news credit CDS {session}",
    f"ARK Invest ARKX space defense ETF news {session}",
    f"bitcoin ethereum price {session}",
    f"leveraged ETF TQQQ QLD Nasdaq 100 {session}",
]


def search(q: str) -> list[dict]:
    if not KEY:
        return []
    try:
        r = requests.get(
            ENDPOINT,
            params={"q": q, "count": 6, "freshness": "pd", "country": "us"},
            headers={"Accept": "application/json", "X-Subscription-Token": KEY},
            timeout=20,
        )
        if r.status_code == 429:
            time.sleep(2)
            return []
        r.raise_for_status()
        results = r.json().get("web", {}).get("results", [])
        return [
            {
                "title": x.get("title"),
                "url": x.get("url"),
                "age": x.get("age"),
                "snippet": (x.get("description") or "")[:500],
            }
            for x in results
        ]
    except Exception as e:                            # noqa: BLE001
        print(f"  ! 검색 실패 ({q[:40]}...): {e!r}")
        return []


def main() -> int:
    if not KEY:
        print("BRAVE_API_KEY 없음 — 뉴스 없이 진행합니다.")
        (OUT / "news.json").write_text(
            json.dumps({"available": False, "items": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        return 0

    items = []
    for q in QUERIES:
        res = search(q)
        print(f"  {len(res):>2}건  {q[:60]}")
        items.append({"query": q, "results": res})
        time.sleep(1.1)                                # 무료 티어 rate limit 보호

    (OUT / "news.json").write_text(
        json.dumps(
            {"available": True, "session_date": session, "items": items},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    total = sum(len(i["results"]) for i in items)
    print(f"\n✅ 뉴스 {total}건 수집 → data/news.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

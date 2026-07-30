"""
4단계 — GitHub Pages 발행

docs/YYYY-MM-DD.html  개별 브리핑 (영구 보존)
docs/index.html       최신 브리핑 + 지난 브리핑 목록
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
DATA = Path("data")
DOCS = Path("docs"); DOCS.mkdir(exist_ok=True)

b = json.loads((DATA / "briefing.json").read_text(encoding="utf-8"))
session = b["session_date"]
today_kst = datetime.now(KST).strftime("%Y-%m-%d")

# 개별 페이지 (KST 발행일 기준 파일명)
page = DOCS / f"{today_kst}.html"
page.write_text(b["html"], encoding="utf-8")
print(f"발행: docs/{today_kst}.html")

# 최신본을 index로 복사하되, 하단에 지난 브리핑 목록을 붙인다
archive = sorted(
    (p for p in DOCS.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].html")),
    reverse=True,
)
links = "\n".join(
    f'<li><a href="{p.name}">{p.stem}</a></li>' for p in archive[:60]
)
nav = f"""
<section style="max-width:680px;margin:0 auto;padding:30px 18px;border-top:1px solid #ddd">
  <h2 style="font-size:1.1rem;margin:0 0 10px">지난 브리핑</h2>
  <ul style="font-family:ui-monospace,monospace;font-size:.9rem;line-height:2;padding-left:20px">
    {links}
  </ul>
</section>
"""

index_html = b["html"]
if "</body>" in index_html:
    index_html = index_html.replace("</body>", nav + "\n</body>")
else:
    index_html += nav
(DOCS / "index.html").write_text(index_html, encoding="utf-8")

# GitHub Pages가 Jekyll 처리를 건너뛰도록
(DOCS / ".nojekyll").write_text("", encoding="utf-8")

# 카톡 메시지에 넣을 최종 URL 조각을 남긴다
(DATA / "page_path.txt").write_text(f"{today_kst}.html", encoding="utf-8")
print(f"index.html 갱신 · 아카이브 {len(archive)}건")

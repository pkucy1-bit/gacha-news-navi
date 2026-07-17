# -*- coding: utf-8 -*-
"""スタンド・ストーンズ (stasto.co.jp) — WordPress。

一覧: /latest_release/ の a > figure img + .term_period + .p-title
  発売月表記例: 「2024年05月, 2026年07月発売」→ 最後の月（最新の発売/再販月）を採用
価格は詳細ページから汎用パーサーで補完。
"""
import re

from bs4 import BeautifulSoup

from . import common

BASE = "https://stasto.co.jp"
LIST_URL = f"{BASE}/latest_release/"
MAKER = "スタンド・ストーンズ"


def parse_list(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for a in soup.find_all("a", href=re.compile(r"/products_ss/")):
        title_el = a.find(class_="p-title")
        if not title_el:
            continue
        m = re.search(r"/products_ss/([^/]+)/?", a.get("href", ""))
        if not m:
            continue
        img = a.find("img")
        period_el = a.find(class_="term_period")
        spec = common.parse_spec(period_el.get_text(strip=True)) if period_el else {}
        items.append({
            "id": f"stasto-{m.group(1)}",
            "maker": MAKER,
            "name": title_el.get_text(strip=True),
            "url": a.get("href") if a.get("href", "").startswith("http")
                   else BASE + a.get("href", ""),
            "image": img.get("src") if img else None,
            "release": spec.get("release"),
            "release_text": (period_el.get_text(strip=True) if period_el else None),
        })
    return items


def parse_detail(html):
    soup = BeautifulSoup(html, "html.parser")
    return {k: v for k, v in common.parse_spec(soup.get_text(" ", strip=True)).items()
            if k in ("price", "variety")}


def fetch(session, db):
    r = common.get(session, LIST_URL)
    items = parse_list(r.text)
    print(f"[stasto] list: {len(items)} items")
    # release は一覧で取れているため、価格が無い新規のみ詳細取得
    new_items = [it for it in items if it["id"] not in db]
    import time
    fetched = 0
    for it in new_items:
        if fetched >= common.MAX_DETAIL:
            break
        time.sleep(common.WAIT_SEC)
        try:
            rd = common.get(session, it["url"])
            it.update(parse_detail(rd.text))
            fetched += 1
        except Exception as e:
            import sys
            print(f"[WARN] stasto detail {it['id']}: {e}", file=sys.stderr)
    print(f"[stasto] detail fetched: {fetched}")
    return items

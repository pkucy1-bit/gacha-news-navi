# -*- coding: utf-8 -*-
"""ターリン・インターナショナル「カプセルコレクション」(tarlin-capsule.jp)。

Nuxt製だがSSRされており、生HTMLに a.card-block / p.card-ttl が含まれる（確認済み）。
一覧: /product/ の a.card-block[href=/product/<ID>] + p.card-ttl + img(/uploads/…)
詳細: 汎用スペックパーサー
"""
import re

from bs4 import BeautifulSoup

from . import common

BASE = "https://tarlin-capsule.jp"
LIST_URL = f"{BASE}/product/"
MAKER = "ターリン・インターナショナル"


def parse_list(html):
    soup = BeautifulSoup(html, "html.parser")
    seen, items = set(), []
    for a in soup.find_all("a", href=re.compile(r"^/product/\d+$")):
        pid = a["href"].rsplit("/", 1)[-1]
        if pid in seen:
            continue
        seen.add(pid)
        title_el = a.find("p", class_="card-ttl")
        if not title_el:
            continue
        img = a.find("img")
        src = img.get("src") if img else None
        items.append({
            "id": f"tarlin-{pid}",
            "maker": MAKER,
            "name": title_el.get_text(strip=True),
            "url": f"{BASE}/product/{pid}",
            "image": (BASE + src) if src and src.startswith("/") else src,
        })
    return items


def parse_detail(html):
    soup = BeautifulSoup(html, "html.parser")
    return common.parse_spec(soup.get_text(" ", strip=True))


def fetch(session, db):
    r = common.get(session, LIST_URL)
    items = parse_list(r.text)
    print(f"[tarlin] list: {len(items)} items")
    return common.enrich_details(session, items, db, parse_detail, "tarlin")

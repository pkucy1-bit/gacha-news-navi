# -*- coding: utf-8 -*-
"""スタジオソータ / SO-TA (so-ta.com) — WordPress。

一覧: /products/capsuletoy/ の a[href*=/products_detail/capsuletoy/] > img + p.text
詳細: 汎用スペックパーサー（発売月・価格・種類数）
"""
import re

from bs4 import BeautifulSoup

from . import common

BASE = "https://www.so-ta.com"
LIST_URL = f"{BASE}/products/capsuletoy/"
MAKER = "SO-TA"


def parse_list(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for a in soup.find_all("a", href=re.compile(r"/products_detail/capsuletoy/")):
        m = re.search(r"/products_detail/capsuletoy/([^/]+)/?", a.get("href", ""))
        name_el = a.find("p", class_="text")
        if not (m and name_el):
            continue
        img = a.find("img")
        href = a.get("href", "")
        items.append({
            "id": f"sota-{m.group(1)}",
            "maker": MAKER,
            "name": name_el.get_text(strip=True),
            "url": href if href.startswith("http") else BASE + href,
            "image": img.get("src") if img else None,
        })
    return items


def parse_detail(html):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    return common.parse_spec(main.get_text(" ", strip=True))


def fetch(session, db):
    r = common.get(session, LIST_URL)
    items = parse_list(r.text)
    print(f"[sota] list: {len(items)} items")
    return common.enrich_details(session, items, db, parse_detail, "sota")

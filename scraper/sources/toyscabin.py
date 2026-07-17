# -*- coding: utf-8 -*-
"""トイズキャビン (toyscabin.com)。

一覧: /product/ の div.textCase > a
  テキスト形式: 「商品名　400円<br>2026年10月　JAN CODE:4589415443672」
一覧だけで名前・価格・発売月・JANが揃うため詳細ページは取得しない。
"""
import re

from bs4 import BeautifulSoup

from . import common

BASE = "https://toyscabin.com"
LIST_URL = f"{BASE}/product/"
MAKER = "トイズキャビン"


def parse_list(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for div in soup.find_all("div", class_="textCase"):
        a = div.find("a")
        if not a:
            continue
        href = a.get("href", "")
        m = re.search(r"/product/([0-9_]+)\.php", href)
        if not m:
            continue
        text = a.get_text("\n", strip=True)
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        if not lines:
            continue
        name_line = lines[0]
        price = None
        pm = re.search(r"([\d,]+)\s*円", name_line)
        if pm:
            price = int(pm.group(1).replace(",", ""))
            name_line = name_line[:pm.start()].strip("　 \t")
        spec = common.parse_spec(" ".join(lines[1:]))
        jan = None
        jm = re.search(r"JAN\s*CODE[:：]\s*(\d+)", text)
        if jm:
            jan = jm.group(1)
        items.append({
            "id": f"toyscabin-{jan or m.group(1)}",
            "maker": MAKER,
            "name": name_line,
            "price": price,
            "url": BASE + href if href.startswith("/") else href,
            "image": None,  # 一覧に画像なし（詳細ページ取得は省略）
            "release": spec.get("release"),
            "release_text": spec.get("release_text"),
        })
    return [it for it in items if it["name"]]


def fetch(session, db):
    r = common.get(session, LIST_URL)
    items = parse_list(r.text)
    print(f"[toyscabin] list: {len(items)} items")
    return items

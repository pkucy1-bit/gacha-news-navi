# -*- coding: utf-8 -*-
"""クオリア (qualia-45.jp)。

一覧: トップページの a[href=/product/view/<ID>]（商品名は一覧に無い）
詳細: <title> / h1 から商品名、本文から汎用スペックパーサー
"""
import re

from bs4 import BeautifulSoup

from . import common

BASE = "https://www.qualia-45.jp"
MAKER = "クオリア"


def parse_list(html):
    soup = BeautifulSoup(html, "html.parser")
    seen, items = set(), []
    for a in soup.find_all("a", href=re.compile(r"/product/view/\d+")):
        m = re.search(r"/product/view/(\d+)", a.get("href", ""))
        pid = m.group(1)
        if pid in seen:
            continue
        seen.add(pid)
        img = a.find("img")
        src = img.get("src") if img else None
        items.append({
            "id": f"qualia-{pid}",
            "maker": MAKER,
            "name": "",  # 詳細ページで補完
            "url": f"{BASE}/product/view/{pid}",
            "image": (BASE + src) if src and src.startswith("/") else src,
        })
    return items


def parse_detail(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    out = common.parse_spec(text)
    # 商品名は「商品名」ラベルの次の行にある（h1/titleには入っていない）
    m = re.search(r"商品名\n+(.+)", text)
    if m:
        out["name"] = m.group(1).strip()
    else:
        h2 = soup.find("h2")
        if h2 and h2.get_text(strip=True) not in ("PRODUCT",):
            out["name"] = h2.get_text(strip=True)
    return out


def fetch(session, db):
    r = common.get(session, BASE + "/")
    items = parse_list(r.text)
    print(f"[qualia] list: {len(items)} items")
    items = common.enrich_details(session, items, db, parse_detail, "qualia")
    # 名前が取れなかった新規アイテムは除外（既知のものは維持）
    return [it for it in items if it.get("name") or it["id"] in db]

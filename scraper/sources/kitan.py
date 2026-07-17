# -*- coding: utf-8 -*-
"""キタンクラブ (kitan.jp) — WordPress。

一覧: /products/ の li.c-productBox__item > a[href=/products/<slug>/]
詳細: dl.c-productDetail__detail-item の dt/dd（商品名/発売元/発売日/サイズ/価格）
"""
import re

from bs4 import BeautifulSoup

from . import common

BASE = "https://kitan.jp"
LIST_URL = f"{BASE}/products/"
MAKER = "キタンクラブ"


def parse_list(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for li in soup.find_all("li", class_="c-productBox__item"):
        a = li.find("a")
        if not a:
            continue
        m = re.search(r"/products/([a-z0-9_\-]+)/?$", a.get("href", ""))
        if not m:
            continue
        img = li.find("img")
        items.append({
            "id": f"kitan-{m.group(1)}",
            "maker": MAKER,
            "name": "",  # 一覧に商品名テキストが無いため詳細で補完
            "url": f"{BASE}/products/{m.group(1)}/",
            "image": img.get("src") if img else None,
        })
    return items


def parse_detail(html):
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for dl in soup.find_all("dl", class_="c-productDetail__detail-item"):
        dt, dd = dl.find("dt"), dl.find("dd")
        if not (dt and dd):
            continue
        key = dt.get_text(strip=True)
        val = dd.get_text(" ", strip=True)
        if key == "商品名":
            out["name"] = val
        elif "発売日" in key:
            out.update({k: v for k, v in common.parse_spec(val).items()
                        if k in ("release", "release_text")})
            out["release_text"] = val
        elif "価格" in key:  # 例: 「1回500円 全5種」
            spec = common.parse_spec(val)
            out.update({k: v for k, v in spec.items() if k in ("price", "variety")})
    if not out.get("name"):
        t = soup.find("title")
        if t:
            out["name"] = t.get_text().split("｜")[0].strip()
    og = soup.find("meta", property="og:description")
    if og and og.get("content"):
        out["description"] = og["content"][:300]
    return out


def fetch(session, db):
    r = common.get(session, LIST_URL)
    items = parse_list(r.text)
    print(f"[kitan] list: {len(items)} items")
    items = common.enrich_details(session, items, db, parse_detail, "kitan")
    return [it for it in items if it.get("name") or db.get(it["id"])]

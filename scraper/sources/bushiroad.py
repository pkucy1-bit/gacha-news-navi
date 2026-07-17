# -*- coding: utf-8 -*-
"""ブシロードクリエイティブ「ブシカプ！」 (capsule.bushiroad-creative.com) — WordPress(SSR)。

トップページから /product/<ID>/ のリンクを収集。
詳細: dl 内の dt/dd（JANコード/発売日/価格/サイズ/種類/対象年齢）
"""
import re

from bs4 import BeautifulSoup

from . import common

BASE = "https://capsule.bushiroad-creative.com"
MAKER = "ブシロードクリエイティブ"


def parse_list(html):
    soup = BeautifulSoup(html, "html.parser")
    seen, items = set(), []
    for a in soup.find_all("a", href=re.compile(r"/product/(\d+)/?")):
        m = re.search(r"/product/(\d+)", a.get("href", ""))
        pid = m.group(1)
        if pid in seen:
            continue
        seen.add(pid)
        img = a.find("img")
        title_el = a.find("p", class_=re.compile("Title"))
        items.append({
            "id": f"bushiroad-{pid}",
            "maker": MAKER,
            "name": (title_el.get_text(strip=True) if title_el
                     else (img.get("alt", "").strip() if img else "")),
            "url": f"{BASE}/product/{pid}/",
            "image": img.get("src") if img else None,
        })
    return [it for it in items if it["name"]]


def parse_detail(html):
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for dl in soup.find_all("dl"):
        text = dl.get_text(" ", strip=True)
        if "発売日" not in text and "JANコード" not in text:
            continue
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            key = dt.get_text(strip=True)
            val = dd.get_text(" ", strip=True)
            if "発売" in key:
                out["release_text"] = val
                out.update({k: v for k, v in common.parse_spec(val).items()
                            if k == "release"})
            elif "価格" in key:
                out.update({k: v for k, v in common.parse_spec(val).items()
                            if k == "price"})
            elif "種類" in key:
                out["variety"] = val
            elif "対象年齢" in key:
                out["age"] = val
        break
    return out


def fetch(session, db):
    r = common.get(session, BASE + "/")
    items = parse_list(r.text)
    print(f"[bushiroad] list: {len(items)} items")
    return common.enrich_details(session, items, db, parse_detail, "bushiroad")

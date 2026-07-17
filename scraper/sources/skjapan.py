# -*- coding: utf-8 -*-
"""エスケイジャパン (sk-japan.co.jp/capsule-toy)。

一覧: /capsule-toy の a[href=/capsule-toy/archive/<YYMM>-<slug>]
  リンクコード例: 2607-shimajiro → 2026年7月
※ページの一部がJSレンダリングの可能性あり。取得0件の場合は警告のみ（無人運用優先）。
"""
import re

from bs4 import BeautifulSoup

from . import common

BASE = "https://www.sk-japan.co.jp"
LIST_URL = f"{BASE}/capsule-toy"
MAKER = "エスケイジャパン"


def parse_list(html):
    soup = BeautifulSoup(html, "html.parser")
    seen, items = set(), []
    for a in soup.find_all("a", href=re.compile(r"/capsule-toy/archive/\d{4}-")):
        m = re.search(r"/capsule-toy/archive/((\d{2})(\d{2})-[a-z0-9\-]+)", a.get("href", ""))
        if not m:
            continue
        code = m.group(1)
        if code in seen:
            continue
        seen.add(code)
        yy, mm = int(m.group(2)), int(m.group(3))
        name = a.get_text(" ", strip=True)
        img = a.find("img")
        items.append({
            "id": f"skjapan-{code}",
            "maker": MAKER,
            "name": re.sub(r"20\d{2}年\d{1,2}月", "", name).strip(),
            "url": f"{BASE}/capsule-toy/archive/{code}",
            "image": img.get("src") if img else None,
            "release": f"20{yy}-{mm:02d}",
            "release_text": f"20{yy}年{mm}月",
        })
    return [it for it in items if it["name"]]


def fetch(session, db):
    r = common.get(session, LIST_URL)
    items = parse_list(r.text)
    if not items:
        print("[WARN] skjapan: 0 items (page may be JS-rendered)")
    else:
        print(f"[skjapan] list: {len(items)} items")
    return items

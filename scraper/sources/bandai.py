# -*- coding: utf-8 -*-
"""バンダイ ガシャポンオフィシャルサイト (gashapon.jp) の新作情報を取得する。

一覧ページ (products/result.php) はサーバーレンダリングされた HTML で、
全商品カード（約500件）が1ページに含まれる。
発売時期・説明文は詳細ページ (products/detail.php?jan_code=...) にのみあるため、
未取得の商品に限り、1回の実行あたり MAX_DETAIL 件まで詳細を取得する。
"""
import re
import sys
import time

from bs4 import BeautifulSoup

BASE = "https://gashapon.jp"
LIST_URL = f"{BASE}/products/result.php"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}
MAX_DETAIL = 40   # 1回の実行で詳細ページを取得する上限（相手サーバーへの負荷対策）
WAIT_SEC = 1.5    # 詳細ページ取得の間隔（秒）


def parse_list(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for a in soup.find_all("a", class_="c-card__link"):
        href = a.get("href", "")
        m = re.search(r"jan_code=(\d+)", href)
        if not m:
            continue
        jan = m.group(1)
        name_el = a.find(class_="c-card__name")
        price_el = a.find(class_="c-card__price--main")
        cat_el = a.find(class_="c-card__category")
        img_el = a.find("img")
        price = None
        if price_el:
            digits = re.sub(r"[^\d]", "", price_el.get_text())
            price = int(digits) if digits else None
        items.append({
            "id": "bandai-" + jan,
            "maker": "バンダイ",
            "name": name_el.get_text(strip=True) if name_el else "",
            "price": price,
            "category": cat_el.get_text(strip=True) if cat_el else "",
            "url": f"{BASE}/products/detail.php?jan_code={jan}",
            "image": img_el.get("src") if img_el else None,
        })
    return items


def parse_detail(html):
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    # 発売時期・種類数・対象年齢は <dl class="pg-detailDefinition"> の dt/dd ペア
    for dl in soup.find_all("dl", class_="pg-detailDefinition"):
        dt = dl.find("dt")
        dd = dl.find("dd")
        if not (dt and dd):
            continue
        key = dt.get_text(strip=True)
        val = dd.get_text(" ", strip=True)
        if "発売" in key:
            out["release_text"] = val
            m = re.search(r"(20\d{2})年\s*(\d{1,2})月", val)
            if m:
                out["release"] = f"{m.group(1)}-{int(m.group(2)):02d}"
        elif "種類" in key:
            out["variety"] = val
        elif "対象年齢" in key:
            out["age"] = val
    desc = soup.find("p", class_="pg-detail__description")
    if desc:
        out["description"] = desc.get_text("\n", strip=True)
    return out


def fetch(session, db):
    r = session.get(LIST_URL, headers=UA, timeout=30)
    r.raise_for_status()
    items = parse_list(r.text)
    print(f"[bandai] list: {len(items)} items")

    fetched = 0
    for it in items:
        known = db.get(it["id"], {})
        if known.get("release_text") or fetched >= MAX_DETAIL:
            continue
        time.sleep(WAIT_SEC)
        try:
            rd = session.get(it["url"], headers=UA, timeout=30)
            rd.raise_for_status()
            it.update(parse_detail(rd.text))
            fetched += 1
        except Exception as e:  # 1件の失敗で全体を止めない
            print(f"[WARN] bandai detail {it['id']}: {e}", file=sys.stderr)
    print(f"[bandai] detail fetched: {fetched}")
    return items

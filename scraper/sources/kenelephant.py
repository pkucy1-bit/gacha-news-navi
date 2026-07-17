# -*- coding: utf-8 -*-
"""ケンエレファント — 公式ストア kenelestore.jp (Shopify) の products.json を利用。

Shopify 標準の公開 JSON エンドポイントなので構造が安定している。
アクセス過多で一時ブロックされることがあるため 1 リクエストのみ・低頻度で使う。
"""
from . import common

BASE = "https://kenelestore.jp"
JSON_URL = f"{BASE}/products.json?limit=50"
MAKER = "ケンエレファント"
# カプセルトイ関連の判定キーワード（product_type / tags に含まれるか）
CAPSULE_KEYWORDS = ("カプセル", "ガチャ", "capsule")


def fetch(session, db):
    r = common.get(session, JSON_URL)
    data = r.json()
    items = []
    for p in data.get("products", []):
        haystack = (p.get("product_type", "") + " " + " ".join(p.get("tags", []))).lower()
        if not any(k.lower() in haystack for k in CAPSULE_KEYWORDS):
            continue
        v = (p.get("variants") or [{}])[0]
        img = (p.get("images") or [{}])[0]
        pub = p.get("published_at") or ""
        items.append({
            "id": f"kenelephant-{p['handle']}",
            "maker": MAKER,
            "name": p.get("title", ""),
            "price": int(float(v["price"])) if v.get("price") else None,
            "url": f"{BASE}/products/{p['handle']}",
            "image": img.get("src"),
            "release": pub[:7] if pub else None,
            "release_text": f"{pub[:4]}年{int(pub[5:7])}月" if len(pub) >= 7 else None,
        })
    print(f"[kenelephant] {len(items)} capsule items")
    return items

# -*- coding: utf-8 -*-
"""Google ニュース検索RSS — 全メーカー横断のキャッチオール。

公式サイトにもPR TIMESにも載らない中小メーカーの新商品情報を、
ニュース記事経由で自動的に拾う。RSSは配信目的の公開フィード。
"""
import hashlib
import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import quote

from . import common

QUERY = '"カプセルトイ" OR "ガチャガチャ" OR "ガシャポン" 新商品 OR 発売'
FEED_URL = (
    "https://news.google.com/rss/search?q=" + quote(QUERY) + "&hl=ja&gl=JP&ceid=JP:ja"
)
MAX_ITEMS = 30
# 明らかに商品情報でないノイズを除外するキーワード
EXCLUDE = ("店舗", "オープン", "開催", "イベント", "決算", "株価")


def parse_feed(xml_text):
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"[WARN] gnews parse: {e}", file=sys.stderr)
        return items
    for el in root.iter("item"):
        title = (el.findtext("title") or "").strip()
        link = (el.findtext("link") or "").strip()
        pub = (el.findtext("pubDate") or "").strip()
        source = (el.findtext("source") or "").strip()
        if not (title and link):
            continue
        if any(k in title for k in EXCLUDE):
            continue
        rid = hashlib.md5(link.encode()).hexdigest()[:16]
        spec = common.parse_spec(title)
        items.append({
            "id": f"gnews-{rid}",
            "kind": "news",
            "maker": source or "ニュース",
            "name": re.sub(r"\s*-\s*[^-]+$", "", title),  # 末尾の「 - 媒体名」を除去
            "url": link,
            "date": pub[:25] or None,
            "release": spec.get("release"),
            "release_text": spec.get("release_text"),
        })
        if len(items) >= MAX_ITEMS:
            break
    return items


def fetch(session, db):
    r = common.get(session, FEED_URL)
    items = parse_feed(r.text)
    print(f"[gnews] {len(items)} items")
    return items

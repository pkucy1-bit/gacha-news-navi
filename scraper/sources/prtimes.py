# -*- coding: utf-8 -*-
"""PR TIMES 公式RSS（会社別）— 公式サイト直取得でカバーできないメーカーの補完。

各社の公開RSS: https://prtimes.jp/companyrdf.php?company_id=<ID>
RSSは配信目的で公開されているため、低頻度取得なら負荷・規約面で安全。

会社IDは PR TIMES のプレスリリースURL（.../p/000000324.000134693.html の後半）から
分かる。新しいメーカーを追加するときは COMPANIES に追記するだけ。
※公式サイト直取得済みのメーカー（バンダイ等11社）は重複を避けるため登録しない。
"""
import re
import sys
import time
import xml.etree.ElementTree as ET

from . import common

# メーカー名: PR TIMES company_id（公式スクレイパー未対応の会社のみ）
COMPANIES = {
    "アイピーフォー": 134693,
    "gray park（灰色メロン）": 143957,
    # 追加例: "メーカー名": 会社ID,
}

KEYWORDS = ("カプセル", "ガチャ", "ガシャ")
FEED_URL = "https://prtimes.jp/companyrdf.php?company_id={}"


def _strip_ns(tag):
    return tag.rsplit("}", 1)[-1]


def parse_feed(xml_text, maker):
    """RSS1.0(RDF) をパースしてカプセルトイ関連のリリースのみ返す。"""
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"[WARN] prtimes parse ({maker}): {e}", file=sys.stderr)
        return items
    for el in root.iter():
        if _strip_ns(el.tag) != "item":
            continue
        fields = {}
        for child in el:
            fields[_strip_ns(child.tag)] = (child.text or "").strip()
        title = fields.get("title", "")
        link = fields.get("link", "")
        if not (title and link):
            continue
        if not any(k in title for k in KEYWORDS):
            continue
        m = re.search(r"/p/(\d+)\.(\d+)\.html", link)
        rid = f"{m.group(2)}-{m.group(1)}" if m else re.sub(r"\W+", "", link)[-24:]
        spec = common.parse_spec(title)
        items.append({
            "id": f"prtimes-{rid}",
            "kind": "news",
            "maker": maker,
            "name": title,
            "url": link,
            "date": (fields.get("date") or "")[:10] or None,
            "release": spec.get("release"),
            "release_text": spec.get("release_text"),
        })
    return items


def fetch(session, db):
    out = []
    for maker, cid in COMPANIES.items():
        try:
            r = common.get(session, FEED_URL.format(cid))
            got = parse_feed(r.text, maker)
            out += got
            print(f"[prtimes] {maker}: {len(got)} items")
        except Exception as e:
            print(f"[WARN] prtimes {maker}: {e}", file=sys.stderr)
        time.sleep(common.WAIT_SEC)
    return out

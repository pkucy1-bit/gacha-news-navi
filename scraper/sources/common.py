# -*- coding: utf-8 -*-
"""各ソース共通のユーティリティ。"""
import re
import sys
import time

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}
TIMEOUT = 30
WAIT_SEC = 1.5      # 連続リクエストの間隔（緩めないこと）
MAX_DETAIL = 20     # 1ソースあたり1回の実行で詳細ページを取る上限


def get(session, url):
    r = session.get(url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return r


def parse_spec(text):
    """ページ本文テキストから 発売時期 / 価格 / 種類数 を正規表現で抽出する汎用パーサー。"""
    out = {}
    # 「2026年7月」「2026年07月発売」など。複数あれば最後（=最新の発売月）を採用
    dates = re.findall(r"(20\d{2})年\s*(\d{1,2})月", text)
    if dates:
        y, m = dates[-1]
        out["release"] = f"{y}-{int(m):02d}"
        out["release_text"] = f"{y}年{int(m)}月"
    m = re.search(r"(?:1回|価格)[^\d]{0,10}([\d,]+)\s*円", text)
    if not m:
        m = re.search(r"([\d,]+)\s*円", text)
    if m:
        try:
            out["price"] = int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    m = re.search(r"全\s*(\d+)\s*種", text)
    if m:
        out["variety"] = f"全{m.group(1)}種"
    return out


def enrich_details(session, items, db, parse_detail, source_name,
                   max_detail=MAX_DETAIL, wait=WAIT_SEC):
    """db に無い（=新規の）アイテムに限り詳細ページを取得してマージする共通処理。"""
    fetched = 0
    for it in items:
        known = db.get(it["id"], {})
        if known.get("release_text") or known.get("release"):
            continue
        if fetched >= max_detail:
            break
        time.sleep(wait)
        try:
            r = get(session, it["url"])
            it.update({k: v for k, v in parse_detail(r.text).items() if v})
            fetched += 1
        except Exception as e:
            print(f"[WARN] {source_name} detail {it['id']}: {e}", file=sys.stderr)
    print(f"[{source_name}] detail fetched: {fetched}")
    return items

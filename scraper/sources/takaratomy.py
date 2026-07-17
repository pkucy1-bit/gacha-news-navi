# -*- coding: utf-8 -*-
"""タカラトミーアーツ ガチャ (takaratomy-arts.co.jp) — 実験的ソース。

作成時点でサイトがメンテナンス中だったため、パーサーは未検証。
ENABLED = False のままなら何もしない（安全側）。
サイト復旧後に構造を確認し、fetch を実装してから True にすること。
"""
ENABLED = False

BASE = "https://www.takaratomy-arts.co.jp"
LIST_URL = f"{BASE}/items/gacha/"


def fetch(session, db):
    if not ENABLED:
        print("[takaratomy] disabled (site structure unverified)")
        return []
    # TODO: サイト復旧後に構造を確認して実装
    return []

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""各メーカーの新作ガチャ情報を収集し data/items.json を更新する。

- 既存データとマージ（id で重複排除、新規項目には first_seen を記録）
- 1つのソースが失敗しても他のソースは処理を続行する（無人運用前提）
"""
import json
import sys
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sources import (  # noqa: E402
    bandai,        # バンダイ（ガシャポン公式）
    bushiroad,     # ブシロードクリエイティブ（ブシカプ！）
    gnews,         # Googleニュース横断（全メーカーのキャッチオール）
    kenelephant,   # ケンエレファント（公式ストアJSON）
    kitan,         # キタンクラブ
    prtimes,       # PR TIMES公式RSS（未対応メーカーの補完）
    qualia,        # クオリア
    skjapan,       # エスケイジャパン
    sota,          # SO-TA（スタジオソータ）
    stasto,        # スタンド・ストーンズ
    takaratomy,    # タカラトミーアーツ（メンテ中・無効）
    tarlin,        # ターリン・インターナショナル
    toyscabin,     # トイズキャビン
)

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "items.json"
SOURCES = [bandai, kitan, kenelephant, bushiroad, toyscabin,
           stasto, sota, tarlin, qualia, skjapan, takaratomy,
           prtimes, gnews]


def load_db():
    if DATA_FILE.exists():
        return {it["id"]: it for it in json.loads(DATA_FILE.read_text(encoding="utf-8"))}
    return {}


def main():
    db = load_db()
    session = requests.Session()
    today = date.today().isoformat()
    new_count = 0

    for src in SOURCES:
        try:
            items = src.fetch(session, db)
        except Exception as e:
            print(f"[WARN] source {src.__name__} failed: {e}", file=sys.stderr)
            continue
        for it in items:
            if it["id"] in db:
                # 既存レコードを保持しつつ、新しく取れた値で上書き
                merged = dict(db[it["id"]])
                merged.update({k: v for k, v in it.items() if v not in (None, "")})
                db[it["id"]] = merged
            else:
                it["first_seen"] = today
                db[it["id"]] = it
                new_count += 1

    items = sorted(
        db.values(),
        key=lambda x: (x.get("first_seen") or "", x.get("release") or ""),
        reverse=True,
    )
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"done: total={len(items)} new={new_count}")


if __name__ == "__main__":
    main()

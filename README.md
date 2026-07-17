# ガチャ新作ナビ — 自動更新型カプセルトイ情報サイト

バンダイ「ガシャポンオフィシャルサイト」等の公開情報を毎日自動収集し、
静的サイトとして自動公開する仕組み一式です。GitHub Actions で完全無人運用できます。

## 対応メーカー（10社・各公式サイトから直接取得）

| メーカー | 取得元 | 状態 |
|---|---|---|
| バンダイ | gashapon.jp（商品検索・約500件/回） | ✅ 検証済み |
| キタンクラブ | kitan.jp/products/ | ✅ 検証済み |
| ケンエレファント | kenelestore.jp（Shopify公式JSON） | ✅ 検証済み |
| ブシロードクリエイティブ | capsule.bushiroad-creative.com | ✅ 検証済み |
| トイズキャビン | toyscabin.com/product/ | ✅ 検証済み |
| スタンド・ストーンズ | stasto.co.jp/latest_release/ | ✅ 検証済み |
| SO-TA（スタジオソータ） | so-ta.com/products/capsuletoy/ | ✅ 検証済み |
| ターリン・インターナショナル | tarlin-capsule.jp/product/（旧エポック系） | ✅ 検証済み |
| クオリア | qualia-45.jp | ✅ 検証済み |
| エスケイジャパン | sk-japan.co.jp/capsule-toy | ⚠️ JSレンダリングの可能性（0件時は警告のみ） |
| タカラトミーアーツ | takaratomy-arts.co.jp | ⏸ サイトメンテナンス中のため無効化（復旧後に有効化） |

パーサーは実サイトから採取したHTML断片によるテスト（scraper/test_parsers.py、12/12 PASS）で検証済み。
1つのソースが落ちても他は動き続ける設計です（無人運用前提）。

### 上記以外の全メーカー（プレスリリース横断で補完）

gacha-island.jp が扱う116社のうち、公式サイトに商品一覧が無い中小メーカーは
以下の2つの横断ソースで自動カバーし、サイトの「業界ニュース」タブに表示します。

- **PR TIMES 公式RSS**（`sources/prtimes.py`）: 会社別の公開RSSから
  カプセルトイ関連リリースのみ抽出。会社IDを `COMPANIES` に足すだけで追加可能
- **Googleニュース検索RSS**（`sources/gnews.py`）: 「カプセルトイ/ガチャガチャ/ガシャポン×新商品/発売」
  のニュースを横断取得する全社キャッチオール

構造化した商品データが必要なメーカーは「ソースの追加方法」に沿って個別追加もできます。

## 構成

```
gacha-news-site/
├── scraper/
│   ├── scrape.py            # 情報収集（data/items.json を更新）
│   ├── generate.py          # 静的サイト生成（site/ に出力）
│   ├── test_parsers.py      # パーサーのテスト
│   └── sources/             # メーカー別スクレイパー（上表の各社）
│       └── common.py        # 共通ユーティリティ（待機・汎用スペック抽出）
├── data/items.json          # 蓄積データ（自動コミットされる）
├── site_config.json         # サイト名・AdSense ID などの設定
├── .github/workflows/update.yml  # 毎日 6:00 JST に自動実行
└── requirements.txt
```

## 公開手順（初回のみ・約15分）

1. **GitHub リポジトリ作成**（Public 推奨）し、このフォルダの中身を push
   ```bash
   cd gacha-news-site
   git init && git add -A && git commit -m "initial"
   git remote add origin https://github.com/<ユーザー名>/<リポジトリ名>.git
   git push -u origin main
   ```
2. **GitHub Pages を有効化**: リポジトリの Settings → Pages → Source を「GitHub Actions」に設定
3. **初回実行**: Actions タブ → update-site → Run workflow
4. 数分後に `https://<ユーザー名>.github.io/<リポジトリ名>/` で公開されます
5. `site_config.json` の `site_url` に公開URLを設定して push（sitemap.xml 生成用）

以後は毎日 6:00 JST に自動でスクレイプ→再生成→デプロイされます（無人運用）。

## AdSense を貼る場合

1. 独自ドメインを取得して Pages に設定（AdSense 審査は独自ドメイン推奨）
2. AdSense 審査に申請し、承認後 `site_config.json` の `adsense_client` に
   `ca-pub-XXXXXXXXXXXXXXXX` を設定して push
   → 自動広告スクリプトと ads.txt が全ページに反映されます

**審査のコツ**: 自動収集データだけでは「独自性の低いコンテンツ」と判定されやすいため、
特集記事・ランキングなど手書きコンテンツを10本程度足してから申請するのが定石です。

## 運用上の注意（重要）

- **スクレイピングの節度**: 詳細ページ取得は1回の実行で最大40件・1.5秒間隔に制限済み。
  この設定は緩めないでください（相手サーバーへの負荷・アクセス拒否リスク）
- **画像の著作権**: 商品画像はメーカーCDNへの直リンク（ホットリンク）です。
  権利は各社に帰属し、掲載中止を求められたら `site_config.json` の
  `show_images` を `false` にしてください。本格運用前にメーカーの
  掲載ガイドライン確認を推奨します
- **利用規約**: 収集元サイトの利用規約・robots.txt を運用前に確認してください
- **免責表記**: フッターに出典・免責を自動表示しています

## ソースの追加方法

`scraper/sources/` に新しいモジュールを作り、`fetch(session, db) -> list[dict]` を実装して
`scrape.py` の `SOURCES` に追加するだけです。返す dict の形式は各ソースを参照。
`common.parse_spec()`（発売月・価格・種類数の汎用抽出）と
`common.enrich_details()`（新規アイテムのみ詳細取得）を使うと簡単に書けます。
タカラトミーアーツは作成時点でサイトメンテナンス中だったため未実装です
（`takaratomy.py` の TODO 参照）。

## ローカルでの動作確認

```bash
pip install -r requirements.txt
python scraper/scrape.py     # データ収集
python scraper/generate.py   # site/ に生成
open site/index.html
```

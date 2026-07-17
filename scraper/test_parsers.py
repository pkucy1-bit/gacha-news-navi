#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""各ソースのパーサーを、実サイトから採取したHTML断片で検証する。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sources import (  # noqa
    bandai, bushiroad, gnews, kitan, prtimes, qualia, skjapan, sota, stasto,
    tarlin, toyscabin,
)

OK = []


def check(name, cond, detail=""):
    OK.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, detail)


# --- bandai (実採取断片) ---
h = '''<a href="detail.php?jan_code=4582770026863000" class="c-card__link">
<p class="c-card__thumb --squre"><img loading="lazy" src="https://bandai-a.akamaihd.net/bc/img/model/b/1000253715_2.jpg" alt=""></p>
<p class="c-card__name">SKZOO ミニチュアパッケージチャーム</p>
<div class="c-card__bottom"><i class="c-card__category --station">ガシャポン</i><p class="c-card__price"><span class="c-card__price--main">400</span></p></div></a>'''
r = bandai.parse_list(h)
check("bandai.list", r and r[0]["name"] == "SKZOO ミニチュアパッケージチャーム" and r[0]["price"] == 400)
h = '''<p class="pg-detail__description">説明。</p>
<dl class="pg-detailDefinition"><dt class="pg-detailDefinition__title">発売時期</dt><dd class="pg-detailDefinition__detail --releaseDate">2026年11月未定</dd></dl>'''
r = bandai.parse_detail(h)
check("bandai.detail", r.get("release") == "2026-11")

# --- kitan (実採取断片) ---
h = '''<li class="c-productBox__item"><a href="https://kitan.jp/products/kobosu_neko/">
<figure class="c-productBox__thum"><img src="https://kitan.jp/wp-content/uploads/2026/07/kobosu_DP.jpg"></figure></a></li>'''
r = kitan.parse_list(h)
check("kitan.list", r and r[0]["id"] == "kitan-kobosu_neko")
h = '''<title>こぼすシリーズ おみそしる-ネコ編-｜株式会社キタンクラブ</title>
<dl class="c-productDetail__detail-item"><dt>商品名</dt><dd>こぼすシリーズ おみそしる-ネコ編-</dd></dl>
<dl class="c-productDetail__detail-item"><dt>発売日</dt><dd>2026年7月中旬</dd></dl>
<dl class="c-productDetail__detail-item"><dt>価格</dt><dd>1回500円 全5種</dd></dl>'''
r = kitan.parse_detail(h)
check("kitan.detail", r.get("name", "").startswith("こぼす") and r.get("price") == 500
      and r.get("variety") == "全5種" and r.get("release") == "2026-07", str(r))

# --- bushiroad (実採取断片) ---
h = '''<a href="https://capsule.bushiroad-creative.com/product/9904/" class="capsuleToy__swiperLink">
<p class="capsuleToy__swiperImg"><img src="https://capsule.bushiroad-creative.com/wordpress/wp-content/uploads/2026/03/jyujyutsu-640x640.jpg" alt="呪術廻戦　コレクションフィギュアRICH"></p>
<p class="capsuleToy__swiperTitle">呪術廻戦　コレクションフィギュアRICH</p></a>'''
r = bushiroad.parse_list(h)
check("bushiroad.list", r and r[0]["id"] == "bushiroad-9904" and "呪術廻戦" in r[0]["name"])
h = '''<dl><dt>JANコード</dt><dd>4570194437358</dd><dt>発売日</dt><dd>2026年7月下旬発売予定</dd>
<dt>価格</dt><dd>500円 (税込)</dd><dt>サイズ</dt><dd>約50mm</dd><dt>種類</dt><dd>全5種</dd><dt>対象年齢</dt><dd>15歳以上</dd></dl>'''
r = bushiroad.parse_detail(h)
check("bushiroad.detail", r.get("release") == "2026-07" and r.get("price") == 500 and r.get("variety") == "全5種", str(r))

# --- toyscabin (実採取断片) ---
h = '''<div class="textCase"><a href="/product/20260706_1455.php">「青春ブタ野郎」シリーズアクリルフォトキーチェーン　400円<br>2026年10月　JAN CODE:4589415443672</a></div>'''
r = toyscabin.parse_list(h)
check("toyscabin.list", r and r[0]["price"] == 400 and r[0]["release"] == "2026-10"
      and r[0]["id"] == "toyscabin-4589415443672" and r[0]["name"].endswith("キーチェーン"), str(r))

# --- stasto (実採取断片) ---
h = '''<a href="https://stasto.co.jp/products_ss/egomusk/"><figure><img src="https://stasto.co.jp/web/wp-content/uploads/2024/01/BlueEye.jpg"></figure>
<div class="term_period">2024年05月, 2026年07月発売</div><div class="p-title">ブルーロック エゴイストアイマスク</div></a>'''
r = stasto.parse_list(h)
check("stasto.list", r and r[0]["release"] == "2026-07" and r[0]["name"].startswith("ブルーロック"), str(r))

# --- sota (実採取断片) ---
h = '''<a href="https://www.so-ta.com/products_detail/capsuletoy/denno_daiku_chess3/" class="btn"><dl class="dl">
<dt><figure class="img"><img src="https://www.so-ta.com/wp-content/uploads/2026/06/img_chess_crear.jpg"></figure></dt>
<dd><p class="text">電脳大工 チェス フィギュアコレクション material ver.</p></dd></dl></a>'''
r = sota.parse_list(h)
check("sota.list", r and r[0]["id"] == "sota-denno_daiku_chess3" and "チェス" in r[0]["name"])

# --- tarlin (実採取断片) ---
h = '''<a href="/product/705" class="card-block small-product" id="card-705"><div class="card-thumb">
<img src="/uploads/small_4_DP_72dpi_a74b89be40.jpg" alt="手のひらネットワーク機器4"></div>
<div class="card-text"><p class="card-ttl">ネットワーク機器メーカー監修 手のひらネットワーク機器4</p></div></a>'''
r = tarlin.parse_list(h)
check("tarlin.list", r and r[0]["id"] == "tarlin-705" and r[0]["image"].startswith("https://tarlin-capsule.jp/uploads/"), str(r))

# --- qualia (実採取断片) ---
h = '''<a href="https://www.qualia-45.jp/product/view/1817"><img src="https://www.qualia-45.jp/media/6/3/6/636_255x296.jpg?t=1"></a>'''
r = qualia.parse_list(h)
check("qualia.list", r and r[0]["id"] == "qualia-1817")
h = '''<div><h2>PRODUCT</h2><p>ライセンス</p><h3>ちいかわ　もこもこポーチ2</h3>
<dl><dt>商品名</dt><dd>ちいかわ　もこもこポーチ2</dd><dt>発売日</dt><dd>2026年7月</dd><dt>価格</dt><dd>500円　全6種</dd></dl></div>'''
r = qualia.parse_detail(h)
check("qualia.detail", r.get("name") == "ちいかわ　もこもこポーチ2" and r.get("price") == 500
      and r.get("release") == "2026-07" and r.get("variety") == "全6種", str(r))

# --- skjapan (実採取断片) ---
h = '''<a href="https://www.sk-japan.co.jp/capsule-toy/archive/2607-shimajiro">2026年7月 しまじろう　ふわふわデニムポーチ</a>'''
r = skjapan.parse_list(h)
check("skjapan.list", r and r[0]["release"] == "2026-07" and "しまじろう" in r[0]["name"], str(r))

# --- prtimes (RSS1.0/RDF 形式) ---
h = '''<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<channel rdf:about="https://prtimes.jp/companyrdf.php?company_id=134693"><title>t</title></channel>
<item rdf:about="https://prtimes.jp/main/html/rd/p/000000324.000134693.html">
<title>PINGU MODERN ポーチコレクションがカプセルトイに登場！2026年8月発売</title>
<link>https://prtimes.jp/main/html/rd/p/000000324.000134693.html</link>
<dc:date>2026-07-15T10:00:00+09:00</dc:date></item>
<item rdf:about="https://prtimes.jp/main/html/rd/p/000000999.000134693.html">
<title>決算のお知らせ</title>
<link>https://prtimes.jp/main/html/rd/p/000000999.000134693.html</link></item>
</rdf:RDF>'''
r = prtimes.parse_feed(h, "アイピーフォー")
check("prtimes.feed", len(r) == 1 and r[0]["id"] == "prtimes-000134693-000000324"
      and r[0]["kind"] == "news" and r[0]["release"] == "2026-08"
      and r[0]["date"] == "2026-07-15", str(r))

# --- gnews (RSS2.0 形式) ---
h = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>news</title>
<item><title>ドリームカプセル、新作カプセルトイを2026年9月発売 - ホビー通信</title>
<link>https://example.com/article/1</link>
<pubDate>Thu, 16 Jul 2026 09:00:00 GMT</pubDate>
<source url="https://hobby.example.com">ホビー通信</source></item>
<item><title>ガチャガチャ専門店が新宿にオープン - 街ニュース</title>
<link>https://example.com/article/2</link></item>
</channel></rss>'''
r = gnews.parse_feed(h)
check("gnews.feed", len(r) == 1 and r[0]["kind"] == "news"
      and r[0]["maker"] == "ホビー通信" and r[0]["release"] == "2026-09"
      and "オープン" not in str(r), str(r))

fails = [n for n, ok in OK if not ok]
print(f"\n{len(OK) - len(fails)}/{len(OK)} passed")
sys.exit(1 if fails else 0)

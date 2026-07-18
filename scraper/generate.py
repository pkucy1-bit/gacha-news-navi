#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""data/items.json から静的サイトを site/ に生成する。

特徴（gacha-island.jp との差別化ポイント）:
- 会員登録不要のお気に入り機能（localStorage）
- 商品ごとの購入リンク自動生成（Amazon/楽天/メルカリ/駿河屋）
- タブUI（新着 / 発売スケジュール / メーカー別 / お気に入り）
- キーワード×メーカー×発売月×商品タイプ×並び替えの複合検索
- ダークモード自動対応・モバイル最適化・軽量静的サイト
- SEO: OGP / JSON-LD(Product) / sitemap.xml
"""
import html
import json
import re
import shutil
import urllib.parse
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "items.json"
CONFIG_FILE = ROOT / "site_config.json"
OUT = ROOT / "site"

NEW_DAYS = 7  # この日数以内に見つけた商品に NEW バッジ

# ---------------------------------------------------------------- 商品タイプ分類
TYPE_RULES = [
    ("キーホルダー・チャーム", ("キーホルダー", "キーチェーン", "チャーム", "ストラップ",
                              "スイング", "根付", "めじるし")),
    ("缶バッジ", ("缶バッジ",)),
    ("アクリルスタンド", ("アクリルスタンド", "アクスタ", "アクリルフォト")),
    ("リング・アクセサリー", ("リング", "ブレスレット", "ネックレス", "アクセサリー",
                            "クリップ", "ヘアゴム", "ピアス", "イヤリング")),
    ("ポーチ・ケース", ("ポーチ", "巾着", "ケース", "袋")),
    ("ぬいぐるみ", ("ぬいぐるみ", "ぬい", "プラッシュ")),
    ("フィギュア", ("フィギュア", "ソフビ", "立体", "まちぼうけ")),
    ("ミニチュア", ("ミニチュア", "ミニCD", "パッケージ", "1/64", "1/12", "手のひら")),
    ("マスコット", ("マスコット",)),
    ("アイマスク・雑貨", ("アイマスク", "タオル", "ミラー", "マーカー", "ウォッチ", "ライト")),
]


def classify_type(name):
    for type_name, keywords in TYPE_RULES:
        if any(k in (name or "") for k in keywords):
            return type_name
    return "その他"


def load():
    items = json.loads(DATA_FILE.read_text(encoding="utf-8")) if DATA_FILE.exists() else []
    for it in items:
        it["type"] = classify_type(it.get("name"))
    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return items, cfg


def e(s):
    return html.escape(str(s or ""))


def is_new(it):
    cut = (date.today() - timedelta(days=NEW_DAYS)).isoformat()
    return (it.get("first_seen") or "") >= cut


# 画像なし・「画像準備中」プレースホルダーの判定
PLACEHOLDER_RE = re.compile(r"noimage|no_image|now_?printing|preparing|準備中|dummy|placeholder", re.I)


def has_real_image(it):
    img = it.get("image")
    return bool(img) and not PLACEHOLDER_RE.search(img)


# ---------------------------------------------------------------- CSS
CSS = """
:root {
  --bg:#f4f6fb; --card:#ffffff; --text:#1b2333; --sub:#6b7590;
  --accent:#e5484d; --accent2:#3b6cf0; --line:#e3e7f2; --chip:#eef1f8;
  --shadow:0 2px 10px rgba(25,35,70,.07);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg:#12151d; --card:#1c2130; --text:#e8ebf5; --sub:#98a0b8;
    --line:#2a3044; --chip:#262c40; --shadow:0 2px 12px rgba(0,0,0,.35);
  }
}
* { box-sizing:border-box; margin:0; padding:0; }
html { scroll-behavior:smooth; }
body { font-family:"Hiragino Sans","Noto Sans JP","Yu Gothic",sans-serif;
  background:var(--bg); color:var(--text); line-height:1.7; }
a { color:inherit; }

header { background:var(--card); border-bottom:1px solid var(--line);
  padding:12px 20px 0; position:sticky; top:0; z-index:20; box-shadow:var(--shadow); }
.brand { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }
.brand a { text-decoration:none; font-weight:800; font-size:1.25rem; letter-spacing:.02em; }
.brand a span { color:var(--accent); }
.brand .desc { color:var(--sub); font-size:.75rem; }
.search { display:flex; gap:8px; margin:10px 0; flex-wrap:wrap; }
.search input[type="search"] { flex:1; min-width:180px; max-width:420px; padding:9px 14px;
  border:1px solid var(--line); border-radius:10px; font-size:.9rem;
  background:var(--bg); color:var(--text); }
.search select { padding:8px 10px; border:1px solid var(--line); border-radius:10px;
  font-size:.82rem; background:var(--bg); color:var(--text); max-width:46vw; }
.search input:focus, .search select:focus { outline:2px solid var(--accent2); border-color:transparent; }
.tabs { display:flex; gap:4px; overflow-x:auto; }
.tab { border:none; background:none; color:var(--sub); font-size:.9rem; font-weight:600;
  padding:10px 14px; cursor:pointer; border-bottom:3px solid transparent; white-space:nowrap; }
.tab.active { color:var(--text); border-bottom-color:var(--accent); }

main { max-width:1140px; margin:0 auto; padding:22px 16px 60px; }
h2 { margin:30px 0 14px; font-size:1.2rem; display:flex; align-items:center; gap:8px; }
h2::before { content:""; width:5px; height:1.1em; background:var(--accent); border-radius:3px; }
#search-count { color:var(--sub); font-size:.85rem; font-weight:400; }

.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(158px,1fr)); gap:14px; }
.card { background:var(--card); border-radius:14px; overflow:hidden; position:relative;
  box-shadow:var(--shadow); transition:transform .15s, box-shadow .15s; }
.card:hover { transform:translateY(-3px); box-shadow:0 6px 18px rgba(25,35,70,.14); }
.card > a { text-decoration:none; display:block; }
.card img { width:100%; aspect-ratio:1; object-fit:cover; background:var(--chip); display:block; }
.card .noimg { width:100%; aspect-ratio:1; background:var(--chip); display:flex;
  align-items:center; justify-content:center; color:var(--sub); font-size:.75rem; }
.card .body { padding:9px 11px 11px; }
.card .maker { font-size:.67rem; color:var(--sub); }
.card .name { font-size:.84rem; font-weight:600; line-height:1.45;
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
  overflow:hidden; min-height:2.5em; }
.card .meta { margin-top:6px; font-size:.76rem; color:var(--sub);
  display:flex; justify-content:space-between; align-items:center; gap:4px; }
.card .price { color:var(--accent); font-weight:700; }
.badge-new { position:absolute; top:8px; left:8px; background:var(--accent); color:#fff;
  font-size:.65rem; font-weight:700; border-radius:6px; padding:2px 7px; z-index:2; }
.fav { position:absolute; top:6px; right:6px; z-index:2; border:none; cursor:pointer;
  background:rgba(255,255,255,.88); border-radius:50%; width:32px; height:32px;
  font-size:1rem; line-height:1; color:#b9c0d4; display:flex; align-items:center; justify-content:center; }
.fav.on { color:#f5b301; }
.chip { display:inline-block; background:var(--chip); color:var(--sub); font-size:.66rem;
  border-radius:6px; padding:1px 7px; }

.detail { background:var(--card); border-radius:16px; padding:26px;
  box-shadow:var(--shadow); max-width:780px; margin:0 auto; position:relative; }
.detail img.hero { max-width:100%; border-radius:12px; margin-bottom:16px; }
.detail h1 { font-size:1.3rem; margin-bottom:6px; line-height:1.5; }
.detail .sub { color:var(--sub); font-size:.85rem; margin-bottom:12px; }
.detail dl { display:grid; grid-template-columns:7.5em 1fr; gap:7px 14px;
  margin:16px 0; font-size:.94rem; }
.detail dt { color:var(--sub); }
.detail .desc { white-space:pre-line; margin-top:8px; }
.buy { margin-top:20px; }
.buy h3 { font-size:.95rem; margin-bottom:10px; color:var(--sub); }
.buy-grid { display:flex; flex-wrap:wrap; gap:8px; }
.btn { display:inline-block; padding:9px 16px; border-radius:10px; text-decoration:none;
  font-weight:600; font-size:.88rem; border:1px solid var(--line); background:var(--bg); }
.btn.primary { background:var(--accent); border-color:var(--accent); color:#fff; }
.btn.share { background:#000; border-color:#000; color:#fff; }
.actions { display:flex; gap:8px; margin-top:16px; flex-wrap:wrap; align-items:center; }
.fav-inline { position:static; width:auto; height:auto; border-radius:10px;
  padding:9px 14px; font-size:.88rem; background:var(--bg); border:1px solid var(--line);
  color:var(--sub); font-weight:600; }
.fav-inline.on { color:#f5b301; border-color:#f5b301; }
.noresult { color:var(--sub); padding:20px 4px; }
.count-note { color:var(--sub); font-size:.8rem; margin:-6px 0 12px; }
.news-list { list-style:none; }
.news-list li { background:var(--card); border-radius:12px; box-shadow:var(--shadow);
  padding:12px 16px; margin-bottom:10px; }
.news-list a { text-decoration:none; font-weight:600; font-size:.92rem; line-height:1.5; }
.news-list a:hover { color:var(--accent2); }
.news-meta { color:var(--sub); font-size:.74rem; margin-top:3px;
  display:flex; gap:10px; flex-wrap:wrap; }

footer { text-align:center; color:var(--sub); font-size:.74rem; padding:30px 16px; }
@media (max-width:560px) {
  .grid { grid-template-columns:repeat(2,1fr); gap:10px; }
  .detail { padding:18px; }
  .detail dl { grid-template-columns:6em 1fr; }
}
"""

FOOTER = """</main>
<footer>
<p>掲載している商品情報は各メーカー公式サイトの公開情報をもとにしています。</p>
<p>商品名・画像等の権利は各メーカーに帰属します。正確な発売情報は各公式サイトをご確認ください。</p>
</footer>
</body>
</html>
"""

# ---------------------------------------------------------------- 共通JS（お気に入り）
FAV_JS = """
<script>
window.GachaFav = (function() {
  var KEY = 'gacha_favs';
  function load() {
    try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch (e) { return []; }
  }
  function save(ids) { try { localStorage.setItem(KEY, JSON.stringify(ids)); } catch (e) {} }
  function has(id) { return load().indexOf(id) !== -1; }
  function toggle(id) {
    var ids = load(); var i = ids.indexOf(id);
    if (i === -1) ids.push(id); else ids.splice(i, 1);
    save(ids); return i === -1;
  }
  function paint(root) {
    (root || document).querySelectorAll('.fav[data-id]').forEach(function(b) {
      var on = has(b.getAttribute('data-id'));
      b.classList.toggle('on', on);
      b.textContent = (b.classList.contains('fav-inline') ? (on ? '★ お気に入り済み' : '☆ お気に入りに追加') : (on ? '★' : '☆'));
    });
  }
  document.addEventListener('click', function(ev) {
    var b = ev.target.closest('.fav[data-id]');
    if (!b) return;
    ev.preventDefault();
    toggle(b.getAttribute('data-id'));
    paint();
    document.dispatchEvent(new CustomEvent('favchange'));
  });
  document.addEventListener('DOMContentLoaded', function() { paint(); });
  return { load: load, has: has, paint: paint };
})();
</script>
"""


def head(cfg, title, desc, depth=0, makers=None, months=None, types=None,
         og_image=None, canonical=None, extra_head=""):
    prefix = "../" * depth
    ads = ""
    if cfg.get("adsense_client"):
        ads = (
            f'<script async src="https://pagead2.googlesyndication.com/pagead/js/'
            f'adsbygoogle.js?client={e(cfg["adsense_client"])}" crossorigin="anonymous"></script>'
        )
    select = ""
    if makers:
        opts = "".join(f'<option value="{e(m)}">{e(m)}</option>' for m in makers)
        select = f'<select id="mk"><option value="">全メーカー</option>{opts}</select>'
    if months:
        opts = "".join(
            f'<option value="{e(m)}">{int(m[:4])}年{int(m[5:7])}月</option>' for m in months
        )
        select += f'<select id="rm"><option value="">発売月：すべて</option>{opts}</select>'
    if types:
        opts = "".join(f'<option value="{e(t)}">{e(t)}</option>' for t in types)
        select += f'<select id="tp"><option value="">商品タイプ：すべて</option>{opts}</select>'
    if makers or months or types:
        select += """<select id="st">
<option value="new">新着順</option>
<option value="price_asc">価格が安い順</option>
<option value="price_desc">価格が高い順</option>
<option value="release_desc">発売月が新しい順</option>
<option value="release_asc">発売月が古い順</option>
</select>"""
    tabs = ""
    if makers:  # indexのみタブを表示
        tabs = """<nav class="tabs">
<button class="tab active" data-tab="new">新着</button>
<button class="tab" data-tab="schedule">発売スケジュール</button>
<button class="tab" data-tab="makers">メーカー別</button>
<button class="tab" data-tab="news">業界ニュース</button>
<button class="tab" data-tab="favs">★ お気に入り</button>
</nav>"""
    og = f"""<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:type" content="website">
{f'<meta property="og:image" content="{e(og_image)}">' if og_image else ''}
{f'<link rel="canonical" href="{e(canonical)}">' if canonical else ''}"""
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
{og}
<link rel="stylesheet" href="{prefix}style.css">
{ads}{extra_head}
</head>
<body>
<header>
<div class="brand"><a href="{prefix}index.html">ガチャ<span>新作</span>ナビ</a>
<span class="desc">{e(cfg["site_description"])}</span></div>
<form class="search" action="{prefix}index.html" method="get">
<input type="search" id="q" name="q" placeholder="商品名・メーカー名で検索">{select}</form>
{tabs}</header>
<main>
"""


def card(it, cfg, depth=0):
    prefix = "../" * depth
    img = (
        f'<img loading="lazy" src="{e(it.get("image"))}" alt="{e(it["name"])}">'
        if cfg.get("show_images") and it.get("image")
        else '<div class="noimg">NO IMAGE</div>'
    )
    price = f'{it["price"]:,}円' if it.get("price") else "-"
    release = e(it.get("release_text") or it.get("release") or "")
    new_badge = '<span class="badge-new">NEW</span>' if is_new(it) else ""
    return f"""<div class="card">{new_badge}<button class="fav" data-id="{e(it["id"])}" aria-label="お気に入り">☆</button>
<a href="{prefix}items/{e(it["id"])}.html">
{img}
<div class="body"><div class="maker">{e(it.get("maker") or "")}</div>
<div class="name">{e(it["name"])}</div>
<div class="meta"><span>{release}</span><span class="price">{price}</span></div>
<div style="margin-top:5px"><span class="chip">{e(it.get("type") or "")}</span></div></div>
</a></div>"""


# ---------------------------------------------------------------- 検索・タブJS（index）
SEARCH_JS = """
<script src="search-data.js"></script>
<script>
(function() {
  var input = document.getElementById('q');
  var select = document.getElementById('mk');
  var monthSel = document.getElementById('rm');
  var typeSel = document.getElementById('tp');
  var sortSel = document.getElementById('st');
  var resultSec = document.getElementById('search-results');
  var browseSec = document.getElementById('browse');
  var grid = document.getElementById('search-grid');
  var count = document.getElementById('search-count');

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }
  function cardHtml(it) {
    var img = it.img
      ? '<img loading="lazy" src="' + esc(it.img) + '" alt="' + esc(it.n) + '">'
      : '<div class="noimg">NO IMAGE</div>';
    var price = it.p ? Number(it.p).toLocaleString() + '円' : '-';
    return '<div class="card"><button class="fav" data-id="' + esc(it.i) + '">☆</button>' +
      '<a href="items/' + esc(it.i) + '.html">' + img +
      '<div class="body"><div class="maker">' + esc(it.m) + '</div>' +
      '<div class="name">' + esc(it.n) + '</div>' +
      '<div class="meta"><span>' + esc(it.r || '') + '</span><span class="price">' + price +
      '</span></div><div style="margin-top:5px"><span class="chip">' + esc(it.t) +
      '</span></div></div></a></div>';
  }
  function norm(s) { return String(s || '').toLowerCase(); }
  function cmp(a, b, key, asc) {
    var av = a[key], bv = b[key];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (av < bv) return asc ? -1 : 1;
    if (av > bv) return asc ? 1 : -1;
    return 0;
  }
  function sortHits(hits, mode) {
    if (mode === 'new') return hits;
    var s = hits.slice();
    if (mode === 'price_asc') s.sort(function(a, b) { return cmp(a, b, 'p', true); });
    if (mode === 'price_desc') s.sort(function(a, b) { return cmp(a, b, 'p', false); });
    if (mode === 'release_asc') s.sort(function(a, b) { return cmp(a, b, 'rel', true); });
    if (mode === 'release_desc') s.sort(function(a, b) { return cmp(a, b, 'rel', false); });
    return s;
  }
  function run() {
    var q = input.value.trim();
    var mk = select ? select.value : '';
    var rm = monthSel ? monthSel.value : '';
    var tp = typeSel ? typeSel.value : '';
    var st = sortSel ? sortSel.value : 'new';
    if (!q && !mk && !rm && !tp && st === 'new') {
      resultSec.style.display = 'none';
      browseSec.style.display = '';
      return;
    }
    var terms = norm(q).split(/\\s+/).filter(Boolean);
    var hits = SEARCH_DATA.filter(function(it) {
      if (mk && it.m !== mk) return false;
      if (rm && it.rel !== rm) return false;
      if (tp && it.t !== tp) return false;
      var hay = norm(it.n) + ' ' + norm(it.m) + ' ' + norm(it.t);
      return terms.every(function(t) { return hay.indexOf(t) !== -1; });
    });
    hits = sortHits(hits, st);
    resultSec.style.display = '';
    browseSec.style.display = 'none';
    count.textContent = '（' + hits.length + '件）';
    grid.innerHTML = hits.map(cardHtml).join('');
    document.getElementById('noresult').style.display = hits.length ? 'none' : '';
    if (window.GachaFav) GachaFav.paint(resultSec);
  }
  var q0 = new URLSearchParams(location.search).get('q') || '';
  if (q0) input.value = q0;
  input.addEventListener('input', run);
  [select, monthSel, typeSel, sortSel].forEach(function(el) {
    if (el) el.addEventListener('change', run);
  });
  input.form.addEventListener('submit', function(ev) { ev.preventDefault(); run(); });
  run();

  // ---- タブ切り替え ----
  var tabs = document.querySelectorAll('.tab');
  function showTab(name) {
    tabs.forEach(function(t) { t.classList.toggle('active', t.getAttribute('data-tab') === name); });
    document.querySelectorAll('.tab-panel').forEach(function(p) {
      p.style.display = (p.id === 'tab-' + name) ? '' : 'none';
    });
    if (name === 'favs') renderFavs();
  }
  tabs.forEach(function(t) {
    t.addEventListener('click', function() { showTab(t.getAttribute('data-tab')); });
  });
  function renderFavs() {
    var ids = window.GachaFav ? GachaFav.load() : [];
    var favGrid = document.getElementById('fav-grid');
    var hits = SEARCH_DATA.filter(function(it) { return ids.indexOf(it.i) !== -1; });
    favGrid.innerHTML = hits.map(cardHtml).join('');
    document.getElementById('fav-empty').style.display = hits.length ? 'none' : '';
    if (window.GachaFav) GachaFav.paint(favGrid.parentNode);
  }
  document.addEventListener('favchange', function() {
    var active = document.querySelector('.tab.active');
    if (active && active.getAttribute('data-tab') === 'favs') renderFavs();
  });
})();
</script>
"""


def build_index(items, cfg, news=None):
    news = news or []
    # 新着タブ: 画像なし・画像準備中の商品は表示しない（他タブ・検索には表示される）
    new_items = [it for it in items if is_new(it) and has_real_image(it)][:30]
    this_month = date.today().strftime("%Y-%m")
    month_now = [it for it in items
                 if it.get("release") == this_month and has_real_image(it)][:30]

    by_month = defaultdict(list)
    for it in items:
        by_month[it.get("release") or "未定・その他"].append(it)
    months = sorted([m for m in by_month if m != "未定・その他"], reverse=True)
    makers_map = defaultdict(list)
    for it in items:
        if it.get("maker"):
            makers_map[it["maker"]].append(it)
    makers = sorted(makers_map)
    types = sorted({it.get("type") for it in items if it.get("type")})

    parts = [head(cfg, cfg["site_name"] + "｜カプセルトイ新作情報",
                  cfg["site_description"], makers=makers, months=months, types=types)]
    parts.append("""<div id="search-results" style="display:none">
<h2>検索結果<span id="search-count"></span></h2>
<p id="noresult" class="noresult" style="display:none">該当する商品が見つかりませんでした。</p>
<div class="grid" id="search-grid"></div></div>
<div id="browse">""")

    # --- 新着タブ（今月発売 → 新着アイテム の順） ---
    parts.append('<section class="tab-panel" id="tab-new">')
    if month_now:
        y, mo = this_month.split("-")
        parts.append(f"<h2>今月（{y}年{int(mo)}月）発売</h2><div class='grid'>")
        parts += [card(it, cfg) for it in month_now]
        parts.append("</div>")
    if new_items:
        parts.append("<h2>新着アイテム</h2><div class='grid'>")
        parts += [card(it, cfg) for it in new_items]
        parts.append("</div>")
    if not new_items and not month_now:
        parts.append('<p class="noresult">新着情報は次回更新時に反映されます。</p>')
    parts.append("</section>")

    # --- スケジュールタブ ---
    parts.append('<section class="tab-panel" id="tab-schedule" style="display:none">')
    for m in months:
        y, mo = m.split("-")
        parts.append(f"<h2>{y}年{int(mo)}月 発売予定</h2><div class='grid'>")
        parts += [card(it, cfg) for it in by_month[m]]
        parts.append("</div>")
    if by_month.get("未定・その他"):
        parts.append("<h2>発売時期未定・その他</h2><div class='grid'>")
        parts += [card(it, cfg) for it in by_month["未定・その他"][:60]]
        parts.append("</div>")
    parts.append("</section>")

    # --- メーカー別タブ ---
    parts.append('<section class="tab-panel" id="tab-makers" style="display:none">')
    for m in makers:
        parts.append(f"<h2>{e(m)}</h2>"
                     f"<p class='count-note'>{len(makers_map[m])}件</p><div class='grid'>")
        parts += [card(it, cfg) for it in makers_map[m][:30]]
        parts.append("</div>")
    parts.append("</section>")

    # --- 業界ニュースタブ（プレスリリース・ニュース横断） ---
    parts.append('<section class="tab-panel" id="tab-news" style="display:none">')
    parts.append("<h2>業界ニュース・新商品発表</h2>")
    parts.append("<p class='count-note'>各メーカーの新商品発表・プレスリリースをまとめています。</p>")
    if news:
        parts.append('<ul class="news-list">')
        for n in news[:50]:
            date_str = e((n.get("date") or "")[:10])
            parts.append(
                f'<li><a href="{e(n["url"])}" target="_blank" rel="noopener nofollow">'
                f'{e(n["name"])}</a>'
                f'<div class="news-meta"><span>{e(n.get("maker") or "")}</span>'
                f'<span>{date_str}</span></div></li>'
            )
        parts.append("</ul>")
    else:
        parts.append('<p class="noresult">ニュースは次回更新時に反映されます。</p>')
    parts.append("</section>")

    # --- お気に入りタブ ---
    parts.append("""<section class="tab-panel" id="tab-favs" style="display:none">
<h2>お気に入り</h2>
<p id="fav-empty" class="noresult">お気に入りはまだありません。商品カードの ☆ を押すと登録できます（会員登録不要）。</p>
<div class="grid" id="fav-grid"></div>
</section>""")

    parts.append("</div>")  # /#browse
    parts.append(FAV_JS)
    parts.append(SEARCH_JS)
    parts.append(FOOTER)
    (OUT / "index.html").write_text("".join(parts), encoding="utf-8")


def buy_links(name):
    q = urllib.parse.quote((name or "").replace("　", " "))
    return [
        ("Amazonで探す", f"https://www.amazon.co.jp/s?k={q}"),
        ("楽天市場で探す", f"https://search.rakuten.co.jp/search/mall/{q}/"),
        ("メルカリで探す", f"https://jp.mercari.com/search?keyword={q}"),
        ("駿河屋で探す", f"https://www.suruga-ya.jp/search?search_word={q}"),
    ]


def build_item_pages(items, cfg):
    d = OUT / "items"
    d.mkdir(parents=True, exist_ok=True)
    base = (cfg.get("site_url") or "").rstrip("/")
    for it in items:
        title = f'{it["name"]}｜{cfg["site_name"]}'
        desc = (it.get("description") or
                f'{it.get("maker","")} {it["name"]} の発売情報').replace("\n", " ")[:120]
        canonical = f"{base}/items/{it['id']}.html" if base else None
        # JSON-LD (Product)
        ld = {
            "@context": "https://schema.org", "@type": "Product",
            "name": it["name"],
            "brand": {"@type": "Brand", "name": it.get("maker") or ""},
        }
        if it.get("image"):
            ld["image"] = it["image"]
        if it.get("price"):
            ld["offers"] = {"@type": "Offer", "priceCurrency": "JPY",
                            "price": it["price"], "availability": "https://schema.org/PreOrder"}
        extra = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'

        parts = [head(cfg, title, desc, depth=1,
                      og_image=it.get("image"), canonical=canonical, extra_head=extra)]
        parts.append('<div class="detail">')
        if is_new(it):
            parts.append('<span class="badge-new">NEW</span>')
        if cfg.get("show_images") and it.get("image"):
            big = it["image"].replace("/img/model/b/", "/img/model/xl/")
            parts.append(f'<img class="hero" src="{e(big)}" alt="{e(it["name"])}">')
        parts.append(f'<h1>{e(it["name"])}</h1>')
        parts.append(f'<p class="sub">{e(it.get("maker") or "")}'
                     f'　<span class="chip">{e(it.get("type") or "")}</span></p>')
        if it.get("description"):
            parts.append(f'<p class="desc">{e(it["description"])}</p>')
        parts.append("<dl>")
        rows = [
            ("メーカー", it.get("maker")),
            ("商品タイプ", it.get("type")),
            ("発売時期", it.get("release_text") or it.get("release")),
            ("価格", f'{it["price"]:,}円（税込）' if it.get("price") else None),
            ("種類数", it.get("variety")),
            ("対象年齢", it.get("age")),
        ]
        for k, v in rows:
            if v:
                parts.append(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>")
        parts.append("</dl>")

        share_text = urllib.parse.quote(f'{it["name"]}（{it.get("maker","")}）')
        share_url = urllib.parse.quote(canonical or "")
        parts.append(f"""<div class="actions">
<a class="btn primary" href="{e(it["url"])}" target="_blank" rel="noopener">公式サイトで見る</a>
<button class="fav fav-inline" data-id="{e(it["id"])}">☆ お気に入りに追加</button>
<a class="btn share" href="https://x.com/intent/post?text={share_text}&url={share_url}"
 target="_blank" rel="noopener">𝕏 で共有</a>
</div>""")
        parts.append('<div class="buy"><h3>オンラインで探す</h3><div class="buy-grid">')
        for label, url in buy_links(it["name"]):
            parts.append(f'<a class="btn" href="{e(url)}" target="_blank" rel="noopener nofollow">{e(label)}</a>')
        parts.append("</div></div>")
        parts.append("</div>")
        parts.append(FAV_JS)
        parts.append(FOOTER)
        (d / f'{it["id"]}.html').write_text("".join(parts), encoding="utf-8")


def build_search_data(items, cfg):
    show = cfg.get("show_images")
    data = [{
        "i": it["id"],
        "n": it.get("name") or "",
        "m": it.get("maker") or "",
        "p": it.get("price"),
        "r": it.get("release_text") or it.get("release") or "",
        "rel": it.get("release"),
        "t": it.get("type") or "その他",
        "img": (it.get("image") if show else None),
    } for it in items]
    js = "const SEARCH_DATA = " + json.dumps(data, ensure_ascii=False) + ";"
    (OUT / "search-data.js").write_text(js, encoding="utf-8")


def build_extras(items, cfg):
    (OUT / "style.css").write_text(CSS, encoding="utf-8")
    if cfg.get("adsense_client"):
        pub = cfg["adsense_client"].replace("ca-", "")
        (OUT / "ads.txt").write_text(
            f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8"
        )
    if cfg.get("site_url"):
        base = cfg["site_url"].rstrip("/")
        urls = [f"{base}/"] + [f"{base}/items/{it['id']}.html" for it in items]
        xml = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        xml += [f"<url><loc>{html.escape(u)}</loc></url>" for u in urls]
        xml.append("</urlset>")
        (OUT / "sitemap.xml").write_text("\n".join(xml), encoding="utf-8")


def main():
    all_items, cfg = load()
    items = [it for it in all_items if it.get("kind") != "news"]
    news = sorted([it for it in all_items if it.get("kind") == "news"],
                  key=lambda x: (x.get("date") or x.get("first_seen") or ""), reverse=True)
    if OUT.exists():
        try:
            shutil.rmtree(OUT)
        except OSError:
            pass  # 消せない環境では上書き生成にフォールバック
    OUT.mkdir(parents=True, exist_ok=True)
    build_index(items, cfg, news=news)
    build_search_data(items, cfg)
    build_item_pages(items, cfg)
    build_extras(items, cfg)
    print(f"generated: {len(items)} products + {len(news)} news -> {OUT}")


if __name__ == "__main__":
    main()

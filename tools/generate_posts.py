#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ガチャ新作ナビ → Instagram カルーセル投稿 自動生成スクリプト

japan.capsule.toy 風のフィード投稿を生成します:
  1枚目   : 表紙 (オレンジ背景 + 波型パネル + 「新作ガチャ N種」)
  2枚目〜 : Vol.N リボン + 方眼紙背景に公式画像の2x2グリッド + NEXTボタン
  最終枚  : サイト誘導のCTAスライド

出力:
  posts/<日付>/01_cover.png, 02_vol1.png, ..., caption.txt
  posts/index.html (一覧ギャラリー)

使い方:
  python3 generate_posts.py --items-json data/items.json   # リポジトリ内で実行(推奨)
  python3 generate_posts.py                                # 公開サイトから取得して生成
  python3 generate_posts.py --limit 8                      # 最新8商品だけ

必要パッケージ: pillow requests beautifulsoup4
日本語フォント: fonts-noto-cjk (無ければ自動ダウンロード)
"""

import argparse
import datetime
import io
import json
import math
import random
import re
import shutil
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

SITE_BASE = "https://pkucy1-bit.github.io/gacha-news-navi/"
SITE_NAME = "ガチャ新作ナビ"

# ---------- 色設定 (参考アカウント風) ----------
COL_ORANGE = "#DE8A2E"   # メインオレンジ
COL_CREAM = "#FBF5EA"    # クリーム
COL_BROWN = "#5B3A1E"    # 文字の焦げ茶
COL_STAR = "#F6C445"     # 星の黄色
COL_GRID = "#EFE6D8"     # 方眼紙の線
COL_RED = "#D6452F"      # カプセル赤

W = H = 1080
PER_SLIDE = 4            # グリッド1枚あたりの商品数
MAX_SLIDES = 18          # 表紙+CTA込みでIG上限20枚以内に
KEEP_DAYS = 14           # 生成物を保持する日数(古い分は自動削除)

BASE_HASHTAGS = [
    "#ガチャガチャ", "#カプセルトイ", "#ガチャ", "#ガシャポン",
    "#新作ガチャ", "#カプセルトイ新作", "#ガチャ活", "#ガチャガチャの森",
    "#gachapon", "#capsuletoy",
]

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
]
FONT_URL = ("https://github.com/notofonts/noto-cjk/raw/main/"
            "Sans/OTF/Japanese/NotoSansCJKjp-Bold.otf")


def find_font(workdir: Path) -> str:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    cached = workdir / "NotoSansCJKjp-Bold.otf"
    if not cached.exists():
        print("フォントをダウンロード中...")
        r = requests.get(FONT_URL, timeout=120)
        r.raise_for_status()
        cached.write_bytes(r.content)
    return str(cached)


# ---------- 商品ページの解析 ----------
LABELS = ["メーカー", "商品タイプ", "発売時期", "価格", "種類数"]


def parse_item(html: str, slug: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    def meta(name):
        tag = (soup.find("meta", attrs={"property": name})
               or soup.find("meta", attrs={"name": name}))
        return (tag.get("content") or "").strip() if tag else ""

    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    if not title:
        title = (meta("og:title") or "").split("｜")[0].strip()

    lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]
    fields = {}
    for i, line in enumerate(lines):
        if line in LABELS and line not in fields and i + 1 < len(lines):
            nxt = lines[i + 1]
            if nxt not in LABELS:
                fields[line] = nxt

    return {
        "slug": slug,
        "title": title,
        "image": meta("og:image"),
        "maker": fields.get("メーカー", ""),
        "release": fields.get("発売時期", ""),
        "price": fields.get("価格", ""),
        "count": fields.get("種類数", ""),
        "url": SITE_BASE + "items/" + slug + ".html",
    }


def fetch_image(url: str) -> Image.Image | None:
    if not url or "no-image" in url.lower():
        return None
    try:
        r = requests.get(url, timeout=60,
                         headers={"User-Agent": "Mozilla/5.0 (post-generator)"})
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception as e:
        print(f"  画像取得失敗: {url} ({e})")
        return None


# ---------- 描画パーツ ----------
def wavy_rect(x0, y0, x1, y1, amp=16, wl=90):
    """波打った縁の長方形ポリゴンの頂点列"""
    pts = []
    for x in range(x0, x1, 20):
        pts.append((x, y0 + amp * math.sin(x / wl)))
    for y in range(y0, y1, 20):
        pts.append((x1 + amp * math.sin(y / wl), y))
    for x in range(x1, x0, -20):
        pts.append((x, y1 + amp * math.sin(x / wl + 2)))
    for y in range(y1, y0, -20):
        pts.append((x0 + amp * math.sin(y / wl + 2), y))
    return pts


def draw_star(d, cx, cy, r, fill):
    pts = []
    for i in range(10):
        ang = math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(ang), cy - rr * math.sin(ang)))
    d.polygon(pts, fill=fill)


def draw_capsule(d, cx, cy, r):
    """ガチャカプセルのイラスト"""
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#FFFFFF",
              outline=COL_BROWN, width=6)
    d.pieslice([cx - r, cy - r, cx + r, cy + r], 180, 360, fill=COL_RED,
               outline=COL_BROWN, width=6)
    d.line([(cx - r, cy), (cx + r, cy)], fill=COL_BROWN, width=6)
    d.ellipse([cx - r * 0.55, cy - r * 0.75, cx - r * 0.15, cy - r * 0.35],
              fill="#FFFFFF")  # ハイライト


def outlined(d, xy, text, font, fill, stroke, sw, anchor="ma"):
    d.text(xy, text, font=font, fill=fill, stroke_width=sw,
           stroke_fill=stroke, anchor=anchor)


def fit_paste(canvas, img, box, bg="#FFFFFF"):
    """boxに収まるよう縮小して中央貼り付け"""
    bw, bh = box[2] - box[0], box[3] - box[1]
    im = img.copy()
    im.thumbnail((bw, bh), Image.LANCZOS)
    canvas.paste(im, (box[0] + (bw - im.width) // 2,
                      box[1] + (bh - im.height) // 2))


# ---------- スライド生成 ----------
def make_cover(items: list[dict], images: dict, n_items: int,
               font_path: str, date_str: str) -> Image.Image:
    img = Image.new("RGB", (W, H), COL_ORANGE)
    d = ImageDraw.Draw(img)
    d.polygon(wavy_rect(60, 55, W - 60, H - 55), fill=COL_CREAM)

    rnd = random.Random(7)
    for _ in range(14):  # 星をちらす
        x, y = rnd.randint(110, W - 110), rnd.randint(430, 900)
        if 260 < x < 820 and 460 < y < 800:
            continue
        draw_star(d, x, y, rnd.randint(12, 22), COL_STAR)

    # 上部: 商品画像を並べる
    thumbs = [images[i["slug"]] for i in items if images.get(i["slug"])][:4]
    if thumbs:
        tw = 210
        total = len(thumbs) * tw + (len(thumbs) - 1) * 18
        x = (W - total) // 2
        for t in thumbs:
            box = (x, 130, x + tw, 130 + 230)
            im = t.copy()
            im.thumbnail((tw, 230), Image.LANCZOS)
            px = box[0] + (tw - im.width) // 2
            py = box[1] + (230 - im.height) // 2
            d.rounded_rectangle([px - 6, py - 6, px + im.width + 6,
                                 py + im.height + 6], radius=14,
                                fill="#FFFFFF", outline="#EADDC8", width=2)
            img.paste(im, (px, py))
            x += tw + 18

    f_date = ImageFont.truetype(font_path, 88)
    f_main = ImageFont.truetype(font_path, 150)
    f_sub = ImageFont.truetype(font_path, 118)
    f_foot = ImageFont.truetype(font_path, 30)

    outlined(d, (W // 2, 408), date_str, f_date, COL_BROWN, "#FFFFFF", 10)
    outlined(d, (W // 2, 520), "新作ガチャ", f_main, COL_BROWN, "#FFFFFF", 14)
    outlined(d, (W // 2 + 60, 700), f"{n_items}種 発売", f_sub, COL_BROWN,
             "#FFFFFF", 12)
    draw_capsule(d, 210, 810, 95)
    d.text((W // 2, 985), f"{SITE_NAME}  |  最新情報は毎日更新",
           font=f_foot, fill="#A08A72", anchor="ma")
    return img


def make_grid_slide(items: list[dict], images: dict, vol: int,
                    font_path: str, is_last: bool) -> Image.Image:
    img = Image.new("RGB", (W, H), "#FFFFFF")
    d = ImageDraw.Draw(img)
    for g in range(0, W, 54):  # 方眼紙
        d.line([(g, 0), (g, H)], fill=COL_GRID, width=1)
        d.line([(0, g), (W, g)], fill=COL_GRID, width=1)

    # 上部オレンジリボン (左が厚く右へ波打ちながら細く)
    pts = [(0, 0), (W, 0), (W, 60)]
    for x in range(W, -1, -20):
        base = 60 + (W - x) / W * 95
        pts.append((x, base + 14 * math.sin(x / 70)))
    pts.append((0, 155))
    d.polygon(pts, fill=COL_ORANGE)
    f_vol = ImageFont.truetype(font_path, 64)
    d.text((90, 42), f"Vol. {vol}", font=f_vol, fill="#FFFFFF")

    # 2x2 グリッド (公式画像に商品名・価格が入っている前提)
    m, gap, top = 26, 14, 200
    cell_w = (W - m * 2 - gap) // 2
    cell_h = 390
    for idx, item in enumerate(items):
        r, c = divmod(idx, 2)
        x0 = m + c * (cell_w + gap)
        y0 = top + r * (cell_h + gap)
        d.rectangle([x0, y0, x0 + cell_w, y0 + cell_h], fill="#FFFFFF",
                    outline="#E4D8C6", width=2)
        im = images.get(item["slug"])
        if im:
            fit_paste(img, im, (x0 + 6, y0 + 6, x0 + cell_w - 6,
                                y0 + cell_h - 6))
        else:
            d.text((x0 + cell_w // 2, y0 + cell_h // 2), "NO IMAGE",
                   font=f_vol, fill="#DDD2C2", anchor="mm")

    if not is_last:  # NEXTボタン
        f_next = ImageFont.truetype(font_path, 40)
        d.rounded_rectangle([830, 1002, 1056, 1062], radius=30,
                            fill=COL_ORANGE)
        d.text((943, 1010), "NEXT ➡", font=f_next, fill="#FFFFFF",
               anchor="ma")
    return img


def make_cta(font_path: str) -> Image.Image:
    img = Image.new("RGB", (W, H), COL_ORANGE)
    d = ImageDraw.Draw(img)
    d.polygon(wavy_rect(60, 55, W - 60, H - 55), fill=COL_CREAM)
    rnd = random.Random(3)
    for _ in range(12):
        draw_star(d, rnd.randint(120, W - 120), rnd.randint(120, 380),
                  rnd.randint(12, 20), COL_STAR)
    f1 = ImageFont.truetype(font_path, 76)
    f2 = ImageFont.truetype(font_path, 100)
    f3 = ImageFont.truetype(font_path, 42)
    draw_capsule(d, W // 2, 300, 110)
    outlined(d, (W // 2, 460), "最新の新作ガチャ情報は", f1, COL_BROWN,
             "#FFFFFF", 8)
    outlined(d, (W // 2, 560), SITE_NAME, f2, COL_RED, "#FFFFFF", 12)
    d.text((W // 2, 720), "発売スケジュール・メーカー別・価格別で\n毎日チェックできます",
           font=f3, fill=COL_BROWN, anchor="ma", align="center")
    label = "プロフィールのリンクからチェック"
    tw = d.textlength(label, font=f3)
    d.rounded_rectangle([(W - tw) // 2 - 50, 855, (W + tw) // 2 + 50, 945],
                        radius=45, fill=COL_BROWN)
    d.text((W // 2, 876), label, font=f3, fill="#FFFFFF", anchor="ma")
    return img


# ---------- キャプション ----------
def make_caption(items: list[dict], date_str: str) -> str:
    tags = list(BASE_HASHTAGS)
    for it in items:
        t = re.sub(r"[^\wぁ-んァ-ヶ一-龠ー]", "", it["maker"])
        if t and "#" + t not in tags:
            tags.append("#" + t)
    body = [
        f"🆕 {date_str} 新作ガチャまとめ",
        "",
        "今回の新作はこちら▼",
        "",
    ]
    for i, it in enumerate(items, 1):
        info = " / ".join(x for x in
                          [it["maker"], it["price"].replace("（税込）", ""),
                           it["release"]] if x)
        body.append(f"{i:02d}. {it['title']}")
        if info:
            body.append(f"　　({info})")
    body += [
        "",
        "気になる新作はあったかな？👀",
        "よかったらコメントで教えてね💬",
        "",
        "▼ 発売日・価格など詳細はプロフィールのリンクから",
        SITE_BASE,
        "",
        "⚠️発売時期は変更になる場合があります⚠️",
        "",
        " ".join(tags[:28]),
    ]
    return "\n".join(body)


def prune_old(out_dir: Path):
    """KEEP_DAYSより古い生成フォルダを削除してリポジトリの肥大化を防ぐ"""
    cutoff = datetime.date.today() - datetime.timedelta(days=KEEP_DAYS)
    for p in out_dir.iterdir():
        if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name):
            try:
                if datetime.date.fromisoformat(p.name) < cutoff:
                    shutil.rmtree(p)
                    print(f"  古い生成物を削除: {p.name}")
            except ValueError:
                pass


# ---------- ギャラリー ----------
def write_gallery(out_dir: Path):
    sets = sorted([p for p in out_dir.iterdir() if p.is_dir()
                   and list(p.glob("*.png"))], reverse=True)
    blocks = []
    for s in sets:
        imgs = "".join(f'<img src="{s.name}/{p.name}" loading="lazy">'
                       for p in sorted(s.glob("*.png")))
        blocks.append(f'''<div class="set"><h2>{s.name}</h2>
<div class="strip">{imgs}</div>
<button onclick="copyCap('{s.name}', this)">キャプションをコピー</button></div>''')
    html = f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Instagram投稿 生成結果｜{SITE_NAME}</title>
<style>
body{{font-family:sans-serif;background:{COL_CREAM};margin:0;padding:16px}}
h1{{font-size:18px;color:{COL_BROWN}}} h2{{font-size:15px;color:{COL_BROWN}}}
.set{{background:#fff;border-radius:12px;padding:12px;margin-bottom:20px;
box-shadow:0 2px 8px rgba(0,0,0,.08)}}
.strip{{display:flex;gap:8px;overflow-x:auto}}
.strip img{{height:300px;border-radius:8px}}
button{{margin-top:10px;padding:10px 16px;border:none;border-radius:8px;
background:{COL_ORANGE};color:#fff;font-size:14px;cursor:pointer}}
</style></head><body>
<h1>Instagram投稿 生成結果</h1>
<p>画像を長押し(右クリック)で保存 → Instagramでカルーセル投稿してください。</p>
{"".join(blocks)}
<script>
async function copyCap(name, btn){{
  const t = await (await fetch(name + '/caption.txt')).text();
  await navigator.clipboard.writeText(t);
  btn.textContent = 'コピーしました!';
  setTimeout(()=>btn.textContent='キャプションをコピー', 1500);
}}
</script></body></html>"""
    (out_dir / "index.html").write_text(html, encoding="utf-8")


# ---------- 組み立て ----------
def build_carousel(items: list[dict], images: dict, out_dir: Path,
                   font_path: str):
    today = datetime.date.today()
    wd = "月火水木金土日"[today.weekday()]
    date_str = f"{today.month}月{today.day}日({wd})"
    set_dir = out_dir / today.strftime("%Y-%m-%d")
    set_dir.mkdir(parents=True, exist_ok=True)

    make_cover(items, images, len(items), font_path,
               date_str).save(set_dir / "01_cover.png", optimize=True)
    n_slides = math.ceil(len(items) / PER_SLIDE)
    for v in range(n_slides):
        chunk = items[v * PER_SLIDE:(v + 1) * PER_SLIDE]
        make_grid_slide(chunk, images, v + 1, font_path,
                        is_last=False).save(
            set_dir / f"{v + 2:02d}_vol{v + 1}.png", optimize=True)
    make_cta(font_path).save(set_dir / f"{n_slides + 2:02d}_cta.png",
                             optimize=True)
    (set_dir / "caption.txt").write_text(make_caption(items, date_str),
                                         encoding="utf-8")
    print(f"生成完了: {set_dir} (表紙+{n_slides}枚+CTA)")


def load_items_json(path: Path) -> list[dict]:
    """data/items.json (スクレイパーの出力) から商品リストを読み込む"""
    data = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for it in data:
        price = it.get("price")
        items.append({
            "slug": it.get("id", ""),
            "title": it.get("name", ""),
            "image": it.get("image", ""),
            "maker": it.get("maker", ""),
            "release": it.get("release_text", "") or it.get("release", ""),
            "price": f"{price}円（税込）" if price else "",
            "count": it.get("variety", ""),
            "url": SITE_BASE + "items/" + it.get("id", "") + ".html",
        })
    return items


def list_remote_slugs() -> list[str]:
    """公開サイトのトップページから商品ページ一覧を取得(新着順)"""
    r = requests.get(SITE_BASE, timeout=60,
                     headers={"User-Agent": "Mozilla/5.0 (post-generator)"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    slugs = []
    for a in soup.find_all("a", href=True):
        m = re.search(r"items/([^/]+)\.html", a["href"])
        if m and m.group(1) not in slugs:
            slugs.append(m.group(1))
    return slugs


def fetch_remote_item(slug: str) -> dict | None:
    url = SITE_BASE + "items/" + slug + ".html"
    try:
        r = requests.get(url, timeout=60,
                         headers={"User-Agent": "Mozilla/5.0 (post-generator)"})
        r.raise_for_status()
        return parse_item(r.text, slug)
    except Exception as e:
        print(f"  取得エラー ({slug}): {e}", file=sys.stderr)
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items-json", default=None,
                    help="data/items.json のパス(リポジトリ内での実行に推奨)")
    ap.add_argument("--items-dir", default=None,
                    help="商品HTMLフォルダ(省略時は公開サイトから取得)")
    ap.add_argument("--out", default="posts")
    ap.add_argument("--all", action="store_true",
                    help="生成済み(_state.json)の商品も含める")
    ap.add_argument("--limit", type=int, default=PER_SLIDE * (MAX_SLIDES - 2),
                    help="最大商品数")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    font_path = find_font(out_dir)

    state_file = out_dir / "_state.json"
    done = set(json.loads(state_file.read_text())) if state_file.exists() else set()
    new_only = not args.all

    # 商品情報の取得元: items.json / ローカルのitemsフォルダ / 公開サイト
    if args.items_json and Path(args.items_json).is_file():
        sources = [(it["slug"], lambda it=it: it)
                   for it in load_items_json(Path(args.items_json))]
    elif args.items_dir and Path(args.items_dir).is_dir():
        sources = [(f.stem, lambda f=f: parse_item(
            f.read_text(encoding="utf-8"), f.stem))
            for f in sorted(Path(args.items_dir).glob("*.html"),
                            key=lambda p: p.stat().st_mtime, reverse=True)]
    else:
        print(f"公開サイトから商品一覧を取得中... ({SITE_BASE})")
        sources = [(slug, lambda s=slug: fetch_remote_item(s))
                   for slug in list_remote_slugs()]

    items, images = [], {}
    for slug, loader in sources:
        if len(items) >= args.limit:
            break
        if new_only and slug in done:
            continue
        try:
            item = loader()
        except Exception as e:
            print(f"  解析エラー ({slug}): {e}", file=sys.stderr)
            continue
        if not item or not item["title"]:
            continue
        img = fetch_image(item["image"])
        if img is None:
            continue  # 画像なし商品はカルーセルに載せない
        items.append(item)
        images[slug] = img
        print(f"  追加: {item['title']}")

    if not items:
        print("新しい商品がありません。生成をスキップします。")
        return

    build_carousel(items, images, out_dir, font_path)
    done.update(i["slug"] for i in items)
    state_file.write_text(json.dumps(sorted(done), ensure_ascii=False,
                                     indent=1), encoding="utf-8")
    prune_old(out_dir)
    write_gallery(out_dir)


if __name__ == "__main__":
    main()

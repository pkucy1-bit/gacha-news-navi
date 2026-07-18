#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ガチャ新作ナビ → Instagram カルーセル投稿 自動生成スクリプト

「ガチャ新作ナビ」オリジナルデザイン:
  ミント×ネイビー×コーラルの配色 / ガチャマシンのブランドアイコン /
  商品ごとに商品名・メーカー・価格・発売時期の情報バー付きカード

構成:
  1枚目   : 表紙 (日付 + 新作N種 + 商品写真)
  2枚目〜 : 商品カード 2x2 (番号バッジ + 情報バー)
  最終枚  : サイト誘導のCTAスライド

出力:
  posts/<日付>/01_cover.png, ..., caption.txt
  posts/index.html (一覧ギャラリー)

使い方:
  python3 generate_posts.py --items-json data/items.json   # リポジトリ内で実行(推奨)
  python3 generate_posts.py                                # 公開サイトから取得して生成

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
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat

JST = datetime.timezone(datetime.timedelta(hours=9))

SITE_BASE = "https://pkucy1-bit.github.io/gacha-news-navi/"
SITE_NAME = "ガチャ新作ナビ"
SITE_URL_SHORT = "pkucy1-bit.github.io/gacha-news-navi"

# ---------- ブランドカラー ----------
BG = "#EDF6F2"        # ミント
NAVY = "#22384F"      # 文字・線
CORAL = "#FF6058"     # メインアクセント
TEAL = "#27B39A"
YELLOW = "#FFC531"
PURPLE = "#8D7BE0"
GRAY = "#6B7A86"
LINE = "#D8E6E0"
BADGE_COLORS = [CORAL, TEAL, YELLOW, PURPLE]

W = H = 1080
S = 2                 # スーパーサンプリング倍率 (2160で描画→1080に縮小)
PER_SLIDE = 4
MAX_SLIDES = 18
KEEP_DAYS = 14

BASE_HASHTAGS = [
    "#ガチャガチャ", "#カプセルトイ", "#ガチャ", "#ガシャポン",
    "#新作ガチャ", "#カプセルトイ新作", "#ガチャ活", "#ガチャガチャの森",
    "#gachapon", "#capsuletoy",
]

FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
]
FONT_REG_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "C:/Windows/Fonts/meiryo.ttc",
]
FONT_URL = ("https://github.com/notofonts/noto-cjk/raw/main/"
            "Sans/OTF/Japanese/NotoSansCJKjp-Bold.otf")


def find_font(candidates, workdir: Path, fallback=None) -> str:
    for p in candidates:
        if Path(p).exists():
            return p
    if fallback:
        return fallback
    cached = workdir / "NotoSansCJKjp-Bold.otf"
    if not cached.exists():
        print("フォントをダウンロード中...")
        r = requests.get(FONT_URL, timeout=120)
        r.raise_for_status()
        cached.write_bytes(r.content)
    return str(cached)


# ---------- 商品データの取得 ----------
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


def load_items_json(path: Path) -> list[dict]:
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
            "price": f"{price}円" if price else "",
            "count": it.get("variety", ""),
            "url": SITE_BASE + "items/" + it.get("id", "") + ".html",
        })
    return items


def list_remote_slugs() -> list[str]:
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


def is_placeholder(img: Image.Image) -> bool:
    """「準備中」等のプレースホルダー画像を判定"""
    im = img.copy()
    im.thumbnail((64, 64))
    px = list(im.getdata())
    if not px:
        return True
    sats = sorted(max(p) - min(p) for p in px)
    mean_sat = sum(sats) / len(sats)
    p95 = sats[int(len(sats) * 0.95)]
    if mean_sat < 8 and p95 < 24:  # ほぼグレースケール
        return True
    q = im.quantize(16).convert("RGB")
    colors = sorted(q.getcolors(64 * 64) or [], reverse=True)
    total = sum(c for c, _ in colors)
    if total and sum(c for c, _ in colors[:2]) / total > 0.95:
        return True
    stat = ImageStat.Stat(im)
    return max(stat.stddev) < 12


def fetch_image(url: str) -> Image.Image | None:
    if not url or "no-image" in url.lower():
        return None
    try:
        r = requests.get(url, timeout=60,
                         headers={"User-Agent": "Mozilla/5.0 (post-generator)"})
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        if is_placeholder(img):
            print(f"  プレースホルダー画像のためスキップ: {url}")
            return None
        return img
    except Exception as e:
        print(f"  画像取得失敗: {url} ({e})")
        return None


# ---------- 描画ユーティリティ (座標は1080基準, sc()で拡大) ----------
def sc(v):
    return int(round(v * S))


class Fonts:
    def __init__(self, bold_path, reg_path):
        self.bold_path, self.reg_path = bold_path, reg_path
        self._cache = {}

    def b(self, size):
        return self._get(self.bold_path, size)

    def r(self, size):
        return self._get(self.reg_path, size)

    def _get(self, path, size):
        key = (path, size)
        if key not in self._cache:
            self._cache[key] = ImageFont.truetype(path, sc(size))
        return self._cache[key]


def new_canvas(bg=BG):
    return Image.new("RGBA", (W * S, H * S), bg)


def finish(canvas: Image.Image) -> Image.Image:
    return canvas.resize((W, H), Image.LANCZOS).convert("RGB")


def card(canvas, box, radius=20, fill="#FFFFFF", outline=None, ow=0,
         shadow=True):
    x0, y0, x1, y1 = [sc(v) for v in box]
    if shadow:
        sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle(
            [x0 + sc(3), y0 + sc(7), x1 + sc(3), y1 + sc(7)],
            radius=sc(radius), fill=(34, 56, 79, 60))
        canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(sc(6))))
    ImageDraw.Draw(canvas).rounded_rectangle(
        [x0, y0, x1, y1], radius=sc(radius), fill=fill,
        outline=outline, width=sc(ow) if ow else 0)


def pill(canvas, d, cx, cy, text, fnt, bg_col, fg_col, pad_x=26, pad_y=10,
         shadow=False):
    tw = d.textlength(text, font=fnt) / S
    th = fnt.size / S
    box = (cx - tw / 2 - pad_x, cy - th / 2 - pad_y,
           cx + tw / 2 + pad_x, cy + th / 2 + pad_y)
    card(canvas, box, radius=(th + pad_y * 2) / 2, fill=bg_col, shadow=shadow)
    d.text((sc(cx), sc(cy - 1)), text, font=fnt, fill=fg_col, anchor="mm")
    return box


def sticker_text(d, cx, cy, text, fnt, fill, shadow_fill=NAVY, off=6,
                 anchor="mm"):
    d.text((sc(cx), sc(cy + off)), text, font=fnt, fill=shadow_fill,
           anchor=anchor)
    d.text((sc(cx), sc(cy)), text, font=fnt, fill=fill, anchor=anchor)


def capsule_icon(d, cx, cy, r, color, ow=3.0):
    box = [sc(cx - r), sc(cy - r), sc(cx + r), sc(cy + r)]
    d.pieslice(box, 180, 360, fill=color)
    d.pieslice(box, 0, 180, fill="#FFFFFF")
    d.ellipse(box, outline=NAVY, width=sc(ow))
    d.line([sc(cx - r), sc(cy), sc(cx + r), sc(cy)], fill=NAVY, width=sc(ow))
    d.ellipse([sc(cx - r * 0.55), sc(cy - r * 0.72),
               sc(cx - r * 0.18), sc(cy - r * 0.35)], fill="#FFFFFF")


def machine_icon(d, cx, top, hgt):
    """ガチャマシンのイラスト (ブランドアイコン)"""
    R = hgt * 0.28
    dome_cy = top + R
    # ドーム
    d.ellipse([sc(cx - R), sc(top), sc(cx + R), sc(top + 2 * R)],
              fill="#FFFFFF", outline=NAVY, width=sc(hgt * 0.018))
    for (rx, ry, col, rr) in [(-0.42, 0.35, TEAL, 0.30),
                              (0.35, 0.42, YELLOW, 0.28),
                              (-0.02, 0.0, CORAL, 0.32)]:
        capsule_icon(d, cx + rx * R, dome_cy + ry * R, R * rr, col,
                     ow=hgt * 0.012)
    # 本体
    bw, bt = R * 1.15, top + 1.86 * R
    bb = top + hgt
    d.rounded_rectangle([sc(cx - bw), sc(bt), sc(cx + bw), sc(bb)],
                        radius=sc(R * 0.28), fill=CORAL, outline=NAVY,
                        width=sc(hgt * 0.018))
    # ハンドル
    kr = R * 0.34
    kcy = bt + (bb - bt) * 0.34
    d.ellipse([sc(cx - kr), sc(kcy - kr), sc(cx + kr), sc(kcy + kr)],
              fill="#FFFFFF", outline=NAVY, width=sc(hgt * 0.015))
    d.line([sc(cx - kr * 0.55), sc(kcy), sc(cx + kr * 0.55), sc(kcy)],
           fill=NAVY, width=sc(hgt * 0.02))
    # 取り出し口
    sw, sh_ = R * 0.5, R * 0.24
    scy = bt + (bb - bt) * 0.76
    d.rounded_rectangle([sc(cx - sw), sc(scy - sh_), sc(cx + sw),
                         sc(scy + sh_)], radius=sc(sh_ * 0.6),
                        fill=NAVY)


def confetti(d, rnd, n, y_range, avoid=None):
    cols = [TEAL, YELLOW, CORAL, PURPLE]
    for _ in range(n):
        x = rnd.randint(50, W - 50)
        y = rnd.randint(*y_range)
        if avoid and avoid[0] < x < avoid[2] and avoid[1] < y < avoid[3]:
            continue
        kind = rnd.random()
        col = rnd.choice(cols)
        if kind < 0.55:
            capsule_icon(d, x, y, rnd.randint(9, 14), col, ow=2.2)
        else:
            r = rnd.randint(4, 7)
            d.ellipse([sc(x - r), sc(y - r), sc(x + r), sc(y + r)], fill=col)


def brand_lockup(canvas, d, F, cx, cy, scale=1.0, center=True):
    """マシンアイコン + サイト名"""
    fnt = F.b(int(34 * scale))
    name_w = d.textlength(SITE_NAME, font=fnt) / S
    icon_h = 52 * scale
    gap = 14 * scale
    total = icon_h * 0.9 + gap + name_w
    x0 = cx - total / 2 if center else cx
    machine_icon(d, x0 + icon_h * 0.45, cy - icon_h / 2, icon_h)
    d.text((sc(x0 + icon_h * 0.9 + gap), sc(cy)), SITE_NAME, font=fnt,
           fill=NAVY, anchor="lm")


def truncate(d, text, fnt, max_w):
    if d.textlength(text, font=fnt) <= sc(max_w):
        return text
    while text and d.textlength(text + "…", font=fnt) > sc(max_w):
        text = text[:-1]
    return text + "…"


def fit_paste(canvas, img, box):
    bx0, by0, bx1, by1 = [sc(v) for v in box]
    bw, bh = bx1 - bx0, by1 - by0
    im = img.copy()
    im.thumbnail((bw, bh), Image.LANCZOS)
    canvas.paste(im, (bx0 + (bw - im.width) // 2, by0 + (bh - im.height) // 2))


def paste_polaroid(canvas, img, cx, cy, size, angle):
    """白フチ+回転+影つきのサムネイル"""
    th = img.copy()
    th.thumbnail((sc(size), sc(size)), Image.LANCZOS)
    pad = sc(10)
    frame = Image.new("RGBA", (th.width + pad * 2, th.height + pad * 2),
                      "#FFFFFF")
    frame.paste(th, (pad, pad))
    ImageDraw.Draw(frame).rectangle(
        [0, 0, frame.width - 1, frame.height - 1], outline=LINE, width=sc(1))
    rot = frame.rotate(angle, expand=True, resample=Image.BICUBIC)
    # 影
    sh = Image.new("RGBA", rot.size, (0, 0, 0, 0))
    alpha = rot.split()[3].point(lambda a: 60 if a > 0 else 0)
    sh.putalpha(alpha)
    sh = Image.composite(Image.new("RGBA", rot.size, (34, 56, 79, 60)),
                         Image.new("RGBA", rot.size, (0, 0, 0, 0)), alpha)
    sh = sh.filter(ImageFilter.GaussianBlur(sc(5)))
    px, py = sc(cx) - rot.width // 2, sc(cy) - rot.height // 2
    canvas.alpha_composite(sh, (px + sc(3), py + sc(7)))
    canvas.alpha_composite(rot, (px, py))


# ---------- スライド ----------
def make_cover(items, images, n_items, F, date_str):
    canvas = new_canvas()
    d = ImageDraw.Draw(canvas)
    rnd = random.Random(11)
    confetti(d, rnd, 16, (120, 1000), avoid=(55, 115, 1025, 1005))

    brand_lockup(canvas, d, F, W / 2, 64)
    card(canvas, (70, 130, W - 70, 905), radius=34)

    # 日付チップ
    pill(canvas, d, W / 2, 205, f"{date_str} の新作情報", F.b(36), CORAL,
         "#FFFFFF", pad_x=34, pad_y=14)

    # タイトル
    sticker_text(d, W / 2, 330, "新作ガチャ", F.b(124), CORAL, NAVY, off=7)
    n_f = F.b(150)
    u_f = F.b(72)
    n_txt = str(n_items)
    n_w = d.textlength(n_txt, font=n_f) / S
    u_w = d.textlength("種 登場", font=u_f) / S
    x0 = W / 2 - (n_w + 16 + u_w) / 2
    sticker_text(d, x0 + n_w / 2, 490, n_txt, n_f, NAVY, "#C9DCD4", off=6)
    d.text((sc(x0 + n_w + 16), sc(515)), "種 登場", font=u_f, fill=NAVY,
           anchor="lm")

    # 商品サムネイル (ポラロイド風)
    thumbs = [images[i["slug"]] for i in items if images.get(i["slug"])][:4]
    xs = {1: [W / 2], 2: [400, 680], 3: [300, 540, 780],
          4: [255, 475, 665, 850]}.get(len(thumbs), [])
    angles = [-5, 3, -3, 5]
    for i, (t, x) in enumerate(zip(thumbs, xs)):
        paste_polaroid(canvas, t, x, 725, 175, angles[i % 4])

    pill(canvas, d, W / 2, 952, "毎日 朝6時 更新", F.b(30), TEAL, "#FFFFFF",
         pad_x=30, pad_y=11)
    d.text((sc(W / 2), sc(1018)), SITE_URL_SHORT, font=F.r(26), fill=GRAY,
           anchor="mm")
    return finish(canvas)


def make_grid_slide(items, images, page, total_pages, F, is_last):
    canvas = new_canvas()
    d = ImageDraw.Draw(canvas)

    # ヘッダー
    brand_lockup(canvas, d, F, 44, 68, scale=0.95, center=False)
    pill(canvas, d, W - 110, 68, f"{page} / {total_pages}", F.b(28), NAVY,
         "#FFFFFF", pad_x=24, pad_y=9)
    d.line([sc(40), sc(118), sc(W - 40), sc(118)], fill=LINE, width=sc(2))

    m, gap, top = 40, 24, 146
    cell_w = (W - m * 2 - gap) / 2
    cell_h = 424
    for idx, item in enumerate(items):
        r, c = divmod(idx, 2)
        x0 = m + c * (cell_w + gap)
        y0 = top + r * (cell_h + gap)
        col = BADGE_COLORS[idx % 4]
        card(canvas, (x0, y0, x0 + cell_w, y0 + cell_h), radius=18)
        # 画像
        im = images.get(item["slug"])
        if im:
            fit_paste(canvas, im, (x0 + 14, y0 + 26, x0 + cell_w - 14,
                                   y0 + 306))
        # 番号バッジ
        num = (page - 1) * PER_SLIDE + idx + 1
        fg = NAVY if col == YELLOW else "#FFFFFF"
        bx = (x0 + 14, y0 - 14, x0 + 92, y0 + 26)
        card(canvas, bx, radius=20, fill=col, shadow=False)
        d.text((sc(x0 + 53), sc(y0 + 5)), f"{num:02d}", font=F.b(28),
               fill=fg, anchor="mm")
        # 情報バー
        d.line([sc(x0 + 18), sc(y0 + 322), sc(x0 + cell_w - 18),
                sc(y0 + 322)], fill=LINE, width=sc(2))
        name = truncate(d, item["title"], F.b(27), cell_w - 40)
        d.text((sc(x0 + 20), sc(y0 + 346)), name, font=F.b(27), fill=NAVY,
               anchor="lm")
        meta = " ・ ".join(x for x in [item["maker"],
                                       item["price"].replace("（税込）", ""),
                                       item["release"]] if x)
        meta = truncate(d, meta, F.r(23), cell_w - 40)
        d.text((sc(x0 + 20), sc(y0 + 384)), meta, font=F.r(23), fill=GRAY,
               anchor="lm")

    # フッター
    d.text((sc(40), sc(1046)), "画像: 各メーカー公式サイトより", font=F.r(20),
           fill=GRAY, anchor="lm")
    tail = "詳細はプロフィールのリンクへ" if is_last else "スワイプして次へ ▶▶"
    d.text((sc(W - 40), sc(1046)), tail, font=F.b(26), fill=CORAL,
           anchor="rm")
    return finish(canvas)


def make_cta(F):
    canvas = new_canvas()
    d = ImageDraw.Draw(canvas)
    rnd = random.Random(5)
    confetti(d, rnd, 14, (80, 480), avoid=(360, 90, 720, 480))

    machine_icon(d, W / 2, 95, 330)
    d.text((sc(W / 2), sc(520)), "毎日 朝6時、新作ガチャ情報を更新中",
           font=F.b(46), fill=NAVY, anchor="mm")
    sticker_text(d, W / 2, 625, SITE_NAME, F.b(104), CORAL, NAVY, off=7)

    feats = [("発売スケジュール", TEAL), ("メーカー別まとめ", YELLOW),
             ("お気に入り登録", PURPLE)]
    fnt = F.b(30)
    widths = [d.textlength(t, font=fnt) / S + 56 for t, _ in feats]
    total = sum(widths) + 20 * 2
    x = (W - total) / 2
    for (t, col), wdt in zip(feats, widths):
        fg = NAVY if col == YELLOW else "#FFFFFF"
        pill(canvas, d, x + wdt / 2, 760, t, fnt, col, fg, pad_x=28,
             pad_y=13)
        x += wdt + 20
    pill(canvas, d, W / 2, 880, "プロフィールのリンクからチェック", F.b(38),
         NAVY, "#FFFFFF", pad_x=44, pad_y=18, shadow=True)
    d.text((sc(W / 2), sc(975)), SITE_URL_SHORT, font=F.r(28), fill=GRAY,
           anchor="mm")
    return finish(canvas)


# ---------- キャプション ----------
def make_caption(items, date_str):
    tags = list(BASE_HASHTAGS)
    for it in items:
        t = re.sub(r"[^\wぁ-んァ-ヶ一-龠ー]", "", it["maker"])
        if t and "#" + t not in tags:
            tags.append("#" + t)
    body = [
        f"🔔 {date_str} の新作ガチャまとめ",
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


# ---------- 後処理 ----------
def prune_old(out_dir: Path):
    cutoff = datetime.datetime.now(JST).date() - datetime.timedelta(
        days=KEEP_DAYS)
    for p in out_dir.iterdir():
        if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name):
            try:
                if datetime.date.fromisoformat(p.name) < cutoff:
                    shutil.rmtree(p)
                    print(f"  古い生成物を削除: {p.name}")
            except ValueError:
                pass


def write_gallery(out_dir: Path):
    sets = sorted([p for p in out_dir.iterdir() if p.is_dir()
                   and list(p.glob("*.png"))], reverse=True)
    blocks = []
    for s_ in sets:
        imgs = "".join(f'<img src="{s_.name}/{p.name}" loading="lazy">'
                       for p in sorted(s_.glob("*.png")))
        blocks.append(f'''<div class="set"><h2>{s_.name}</h2>
<div class="strip">{imgs}</div>
<button onclick="copyCap('{s_.name}', this)">キャプションをコピー</button></div>''')
    html = f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Instagram投稿 生成結果｜{SITE_NAME}</title>
<style>
body{{font-family:sans-serif;background:{BG};margin:0;padding:16px}}
h1{{font-size:18px;color:{NAVY}}} h2{{font-size:15px;color:{NAVY}}}
.set{{background:#fff;border-radius:12px;padding:12px;margin-bottom:20px;
box-shadow:0 2px 8px rgba(34,56,79,.12)}}
.strip{{display:flex;gap:8px;overflow-x:auto}}
.strip img{{height:300px;border-radius:8px}}
button{{margin-top:10px;padding:10px 16px;border:none;border-radius:8px;
background:{CORAL};color:#fff;font-size:14px;cursor:pointer}}
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
def build_carousel(items, images, out_dir: Path, F: Fonts):
    today = datetime.datetime.now(JST).date()
    wd = "月火水木金土日"[today.weekday()]
    date_str = f"{today.month}月{today.day}日({wd})"
    set_dir = out_dir / today.strftime("%Y-%m-%d")
    set_dir.mkdir(parents=True, exist_ok=True)

    n_slides = math.ceil(len(items) / PER_SLIDE)
    make_cover(items, images, len(items), F, date_str).save(
        set_dir / "01_cover.png", optimize=True)
    for v in range(n_slides):
        chunk = items[v * PER_SLIDE:(v + 1) * PER_SLIDE]
        make_grid_slide(chunk, images, v + 1, n_slides, F,
                        is_last=(v == n_slides - 1)).save(
            set_dir / f"{v + 2:02d}_page{v + 1}.png", optimize=True)
    make_cta(F).save(set_dir / f"{n_slides + 2:02d}_cta.png", optimize=True)
    (set_dir / "caption.txt").write_text(make_caption(items, date_str),
                                         encoding="utf-8")
    print(f"生成完了: {set_dir} (表紙+{n_slides}枚+CTA)")


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
    bold = find_font(FONT_BOLD_CANDIDATES, out_dir)
    reg = find_font(FONT_REG_CANDIDATES, out_dir, fallback=bold)
    F = Fonts(bold, reg)

    state_file = out_dir / "_state.json"
    done = set(json.loads(state_file.read_text())) if state_file.exists() else set()
    new_only = not args.all

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
        sources = [(slug, lambda s_=slug: fetch_remote_item(s_))
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
            continue
        items.append(item)
        images[slug] = img
        print(f"  追加: {item['title']}")

    if not items:
        print("新しい商品がありません。生成をスキップします。")
        return

    build_carousel(items, images, out_dir, F)
    done.update(i["slug"] for i in items)
    state_file.write_text(json.dumps(sorted(done), ensure_ascii=False,
                                     indent=1), encoding="utf-8")
    prune_old(out_dir)
    write_gallery(out_dir)


if __name__ == "__main__":
    main()

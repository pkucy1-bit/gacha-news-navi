# -*- coding: utf-8 -*-
"""
ガチャ新作ナビ → TikTok 写真投稿 (GitHub Actions用 / 公式 Content Posting API)

毎日18時(JST)にGitHub Actionsから実行され、posts/latest.json の画像を
写真カルーセルとしてTikTokに投稿する。

必要な環境変数 (リポジトリのActions Secretsに設定):
  TIKTOK_CLIENT_KEY    : アプリのClient key
  TIKTOK_CLIENT_SECRET : アプリのClient secret

トークンは tiktok_token.json (ワークフローが暗号化ファイルから復号したもの) を使い、
更新された場合は再暗号化してコミットされる。
"""

import os
import sys
import json
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.environ.get("TIKTOK_TOKEN_PATH", os.path.join(ROOT, "tiktok_token.json"))
STATE_FILE = os.path.join(ROOT, "data", "tiktok_last_posted.txt")
LATEST_JSON = os.path.join(ROOT, "site", "posts", "latest.json")  # ビルド済みならローカル参照
LATEST_JSON_URL = "https://pkucy1-bit.github.io/gacha-news-navi/posts/latest.json"
MAX_IMAGES = 35
TITLE_LIMIT = 90
CAPTION_LIMIT = 3900  # 上限4000(UTF-16換算)に対して安全マージンを取る
API_BASE = "https://open.tiktokapis.com"


def get_credentials():
    key = os.environ.get("TIKTOK_CLIENT_KEY", "")
    secret = os.environ.get("TIKTOK_CLIENT_SECRET", "")
    if not key or not secret:
        print("❌ TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET が設定されていません。")
        sys.exit(1)
    return key, secret


def save_token(data):
    data["obtained_at"] = int(time.time())
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_access_token():
    if not os.path.exists(TOKEN_PATH):
        print("❌ tiktok_token.json がありません。復号ステップを確認してください。")
        sys.exit(1)
    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        tok = json.load(f)

    expires_at = tok.get("obtained_at", 0) + tok.get("expires_in", 0)
    if time.time() < expires_at - 600:
        return tok["access_token"]

    print("🔄 アクセストークンを更新しています...")
    key, secret = get_credentials()
    res = requests.post(f"{API_BASE}/v2/oauth/token/", data={
        "client_key": key,
        "client_secret": secret,
        "grant_type": "refresh_token",
        "refresh_token": tok["refresh_token"],
    }, timeout=30)
    data = res.json()
    if "access_token" not in data:
        print(f"❌ トークン更新に失敗しました。ローカルで --auth からやり直してください: {data}")
        sys.exit(1)
    save_token(data)
    return data["access_token"]


def fetch_manifest():
    if os.path.exists(LATEST_JSON):
        with open(LATEST_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    res = requests.get(LATEST_JSON_URL, timeout=30)
    if res.status_code != 200:
        print(f"⚠️ latest.json が見つかりません (HTTP {res.status_code})。スキップします。")
        return None
    return res.json()


def utf16_len(s):
    """TikTokの文字数制限はUTF-16単位(絵文字は2文字扱い)のため専用で数える。"""
    return len(s.encode("utf-16-le")) // 2


def trim_utf16(s, limit):
    while utf16_len(s) > limit and s:
        s = s[:-50] if len(s) > 50 else s[:-1]
    return s


def trim_caption(caption, limit=CAPTION_LIMIT):
    if utf16_len(caption) <= limit:
        return caption
    lines = caption.rstrip().split("\n")
    tags = lines[-1] if lines[-1].startswith("#") else ""
    body_limit = limit - (utf16_len(tags) + 2 if tags else 0)
    body = "\n".join(lines[:-1] if tags else lines)
    if utf16_len(body) > body_limit:
        body = trim_utf16(body, body_limit - 1).rstrip() + "…"
    return body + ("\n\n" + tags if tags else "")


def make_title(caption, date):
    first = caption.strip().split("\n")[0].strip()
    if not first:
        first = f"{date} の新作ガチャまとめ"
    return trim_utf16(first, TITLE_LIMIT)


def already_posted(date):
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() == str(date)
    return False


def mark_posted(date):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(str(date))


def api_post(token, path, body):
    res = requests.post(f"{API_BASE}{path}", json=body, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }, timeout=60)
    return res.json()


def choose_privacy(token):
    data = api_post(token, "/v2/post/publish/creator_info/query/", {})
    err = data.get("error", {})
    if err.get("code") not in (None, "ok"):
        print(f"❌ アカウント情報の取得に失敗しました: {err}")
        sys.exit(1)
    options = data.get("data", {}).get("privacy_level_options", [])
    if "PUBLIC_TO_EVERYONE" in options:
        return "PUBLIC_TO_EVERYONE"
    print("⚠️ アプリ審査前のため「自分のみ公開」で投稿します。")
    return "SELF_ONLY" if "SELF_ONLY" in options else (options[0] if options else "SELF_ONLY")


def post_photos(token, title, description, image_urls, privacy):
    body = {
        "media_type": "PHOTO",
        "post_mode": "DIRECT_POST",
        "post_info": {
            "title": title,
            "description": description,
            "privacy_level": privacy,
            "disable_comment": False,
            "auto_add_music": True,
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "photo_images": image_urls,
            "photo_cover_index": 0,
        },
    }
    data = api_post(token, "/v2/post/publish/content/init/", body)
    err = data.get("error", {})
    if err.get("code") not in (None, "ok"):
        print(f"❌ 投稿リクエストに失敗しました: {err}")
        sys.exit(1)
    return data["data"]["publish_id"]


def wait_publish(token, publish_id, timeout=600):
    print("⏳ TikTok側の処理完了を待っています...")
    end = time.time() + timeout
    while time.time() < end:
        data = api_post(token, "/v2/post/publish/status/fetch/", {"publish_id": publish_id})
        status = data.get("data", {}).get("status", "")
        if status == "PUBLISH_COMPLETE":
            return True
        if status in ("FAILED", "PUBLISH_FAILED"):
            print(f"❌ 投稿に失敗しました: {data.get('data', {}).get('fail_reason', data)}")
            return False
        time.sleep(15)
    print("⚠️ 処理完了を確認できませんでした(タイムアウト)。")
    return False


def main():
    manifest = fetch_manifest()
    if manifest is None:
        return

    date = manifest.get("date", "")
    caption = trim_caption(manifest.get("caption", ""))
    title = make_title(caption, date)
    images = manifest.get("images", [])

    if not images:
        print("❌ latest.json に画像がありません。")
        return

    if already_posted(date):
        print(f"⏭️  {date} は投稿済みです。スキップします。")
        return

    if len(images) > MAX_IMAGES:
        images = images[: MAX_IMAGES - 1] + [images[-1]]

    # TikTok写真投稿はPNG非対応のため、ビルド時に生成したJPEG版のURLを使う
    images = [u[:-4] + ".jpg" if u.lower().endswith(".png") else u for u in images]

    token = get_access_token()
    privacy = choose_privacy(token)

    print(f"📤 写真投稿を作成します: {date} / {len(images)}枚 / 公開範囲={privacy}")
    publish_id = post_photos(token, title, caption, images, privacy)
    print(f"🆔 publish_id: {publish_id}")

    if wait_publish(token, publish_id):
        mark_posted(date)
        print(f"🎉 投稿完了: {date}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()

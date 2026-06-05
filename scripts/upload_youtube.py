"""
upload_youtube.py — YouTube Data API v3 アップローダー

  python scripts/upload_youtube.py --video build/chapters/ch1.mp4 \
      --meta scenes/ch1_meta.json [--schedule 2026-06-10T18:00:00+09:00]

OAuth2 トークンは初回のみブラウザ認証 → token_youtube.json にキャッシュ。
2回目以降は自動リフレッシュ。

meta JSON フォーマット:
  {
    "title":       "第一章 バベルの塔 ── なぜ文明は分裂するのか",
    "description": "...",
    "tags":        ["宗教改革","ドキュメンタリー","歴史"],
    "category_id": "27",          // 27=Education, 22=People&Blogs, 28=Science
    "privacy":     "private",     // private|unlisted|public
    "thumbnail":   "assets/images/tower_of_babel.jpg",  // 任意
    "playlist_id": "PLxxxxxxxx"   // 任意
  }
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent

# OAuth2スコープ（アップロード + プレイリスト操作）
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]
SECRET_FILE  = BASE / "client_secret_youtube.json"
TOKEN_FILE   = BASE / "token_youtube.json"
CHUNK_SIZE   = 256 * 1024 * 10  # 2.5MB チャンク


def _build_service():
    """認証済みYouTube APIサービスを返す。初回はブラウザ認証フローを起動。"""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        print("依存未インストール: pip install google-auth google-auth-oauthlib google-api-python-client")
        sys.exit(1)

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not SECRET_FILE.exists():
                print(f"ERROR: {SECRET_FILE} が見つかりません。")
                print("Google Cloud Console → 認証情報 → OAuth2クライアントID(デスクトップ) でダウンロードして配置してください。")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(SECRET_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
        print(f"  [auth] トークンを {TOKEN_FILE} に保存しました。")

    return build("youtube", "v3", credentials=creds)


def upload(video_path: str, meta: dict, schedule_dt: datetime = None) -> str:
    """
    動画をアップロードしてビデオIDを返す。
    schedule_dt: UTC datetimeを渡すと予約投稿（privacyはprivateで送り後で変更）。
    """
    from googleapiclient.http import MediaFileUpload

    youtube = _build_service()

    privacy = meta.get("privacy", "private")
    body = {
        "snippet": {
            "title":       meta["title"],
            "description": meta.get("description", ""),
            "tags":        meta.get("tags", []),
            "categoryId":  str(meta.get("category_id", "27")),
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    # 予約投稿
    if schedule_dt:
        body["status"]["privacyStatus"] = "private"
        body["status"]["publishAt"] = schedule_dt.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )

    media = MediaFileUpload(video_path, chunksize=CHUNK_SIZE, resumable=True,
                            mimetype="video/mp4")
    print(f"  [upload] {Path(video_path).name} → YouTube ({privacy})")
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  [upload] {pct}%...", end="\r")
    video_id = resp["id"]
    print(f"  [upload] 完了: https://youtu.be/{video_id}")

    # サムネイル設定（チャンネル確認済みの場合のみ可能）
    thumb = meta.get("thumbnail")
    if thumb and Path(thumb).exists():
        if not Path(thumb).is_absolute():
            thumb = str(BASE / thumb)
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumb, mimetype="image/jpeg"),
            ).execute()
            print(f"  [thumb] 設定済み: {Path(thumb).name}")
        except Exception as e:
            print(f"  [thumb] スキップ（チャンネル確認が必要）: {e}")

    # プレイリストに追加
    playlist_id = meta.get("playlist_id")
    if playlist_id:
        youtube.playlistItems().insert(
            part="snippet",
            body={"snippet": {"playlistId": playlist_id,
                              "resourceId": {"kind": "youtube#video", "videoId": video_id}}},
        ).execute()
        print(f"  [playlist] 追加済み: {playlist_id}")

    return video_id


def main():
    ap = argparse.ArgumentParser(description="YouTube アップロード")
    ap.add_argument("--video",    required=True,  help="アップロードする動画ファイル")
    ap.add_argument("--meta",     required=True,  help="メタデータJSON（scenes/*_meta.json）")
    ap.add_argument("--schedule", default=None,   help="予約投稿日時 (ISO8601, 例: 2026-06-10T18:00:00+09:00)")
    args = ap.parse_args()

    meta = json.loads(Path(args.meta).read_text())
    schedule_dt = datetime.fromisoformat(args.schedule) if args.schedule else None

    video_id = upload(args.video, meta, schedule_dt)
    print(f"\nYouTube動画ID: {video_id}")
    print(f"URL: https://youtu.be/{video_id}")


if __name__ == "__main__":
    main()

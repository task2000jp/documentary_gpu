"""
gen_metadata.py — YouTubeメタデータ自動生成（Loop B）

  python scripts/gen_metadata.py scenes/ch6.json \
      [--brief scenes/ch6_brief.md] \
      [--keywords "宗教改革 わかりやすい,ルター 95ヶ条"] \
      [--work 勝利の福音] [--privacy private]

scene JSON（タイミング＋テキスト）＋ ブリーフ ＋ 戦略キーワード を
Groq(llama-3.3-70b) に渡し、SEO最適化メタデータを生成 → scenes/<name>_meta.json。

出力は upload_youtube.py がそのまま食える形式（title/description/tags/...）。
章タイムスタンプは scene JSON から完全自動算出して description に埋め込む。
Groq不可時はテンプレートにフォールバック（必ず何か出力する）。

設計根拠: docs/marketing_system.md
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE = Path(__file__).parent.parent
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"  # メタ品質重視（RPD=1000で十分）

CATEGORY_EDUCATION = "27"


# ─────────────────────────────────────────────
# scene JSON 解析：章タイムスタンプ・画面テキスト抽出
# ─────────────────────────────────────────────
def _fmt_ts(sec: float) -> str:
    s = int(round(sec))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def analyze_scenes(scenes: list) -> dict:
    """累積時間から章マーカーと全画面テキストを抽出。"""
    t = 0.0
    chapters = []   # [(start_sec, name)]
    texts = []      # 画面に出る全テキスト（内容シグナル）
    for s in scenes:
        text = s.get("text") or {}
        content = (text.get("content") or "").strip()
        if content:
            texts.append(content)
            if text.get("style") == "title":
                chapters.append((t, content.replace("\n", " ")))
        t += float(s.get("duration", 0))
    total = t

    # YouTubeチャプター: 先頭0:00必須・3つ以上・各10秒以上
    ts_block = ""
    if len(chapters) >= 3:
        if chapters[0][0] > 0.5:
            chapters.insert(0, (0.0, "オープニング"))
        lines = [f"{_fmt_ts(st)} {name}" for st, name in chapters]
        ts_block = "\n".join(lines)

    return {"chapters_block": ts_block, "onscreen_texts": texts, "total_sec": total}


# ─────────────────────────────────────────────
# Groq 呼び出し
# ─────────────────────────────────────────────
def _call_groq(prompt: str) -> str | None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("  [gen_metadata] GROQ_API_KEY未設定 → テンプレートにフォールバック")
        return None
    payload = json.dumps({
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(
        GROQ_URL, data=payload,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json",
                 # urllibのデフォルトUAはCloudflareにブロックされる(403 1010)
                 "User-Agent": "documentary-gpu/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        print(f"  [gen_metadata] Groq HTTPエラー {e.code}: {e.read()[:200]} → フォールバック")
    except Exception as e:
        print(f"  [gen_metadata] Groqエラー: {e} → フォールバック")
    return None


def _build_prompt(work: str, chapter: str, brief: str,
                  onscreen: list, keywords: list) -> str:
    texts = "\n".join(f"- {t}" for t in onscreen[:25]) or "（画面テキストなし）"
    kw = "、".join(keywords) if keywords else "（指定なし）"
    return f"""あなたは日本のYouTube SEOと知的ドキュメンタリーのマーケティング専門家です。
以下の章のYouTubeメタデータを生成してください。

【作品】{work}
（信仰 × 経済史 × 技術 を統合した知的・厳粛な神学ドキュメンタリー。
  娯楽的な釣りは厳禁。誠実な知的好奇心でフックする。）

【この動画/章】{chapter}

【内容ブリーフ】
{brief or "（ブリーフなし。画面テキストから推定すること）"}

【画面に出るテキスト（内容の手がかり）】
{texts}

【狙う検索キーワード】{kw}

要件:
- title: 「問い」型・好奇心ギャップ・全角28字前後・キーワードを前寄せ。釣りは禁止。
- title_alternatives: A/Bテスト用に異なる切り口で2案。
- description_body: 最初の2行で強くフック（検索結果に出る部分）。その後に内容要約。
  ※チャプター時刻やハッシュタグはここに書かない（システムが付加する）。
- tags: 広域語 + ロングテール日本語を混ぜて10〜15個。
- hashtags: #付き日本語を3〜5個（説明欄末尾用）。
- pinned_comment: 視聴者の対話を促す問いを1つ。
- thumbnail_text: サムネに重ねる短い語句（10字以内）。

必ず次のJSON形式のみで返す（説明文・コードブロック不要）:
{{"title":"...","title_alternatives":["...","..."],"description_body":"...","tags":["..."],"hashtags":["#..."],"pinned_comment":"...","thumbnail_text":"..."}}"""


# ─────────────────────────────────────────────
# 説明文の組み立て
# ─────────────────────────────────────────────
def compose_description(body: str, chapters_block: str,
                        hashtags: list, work: str) -> str:
    parts = [body.strip()]
    if chapters_block:
        parts.append("🕐 チャプター\n" + chapters_block)
    parts.append(f"━━━━━━━━━━━━━━\nドキュメンタリー「{work}」\nチャンネル登録で続きをご覧ください。")
    if hashtags:
        parts.append(" ".join(hashtags))
    return "\n\n".join(parts)


def _fallback(work: str, chapter: str, onscreen: list) -> dict:
    """Groq不可時の最小メタデータ。"""
    title = f"{chapter} ──「{work}」"
    body = f"{work} より「{chapter}」。\n\n" + "　".join(onscreen[:3])
    return {
        "title": title[:60],
        "title_alternatives": [],
        "description_body": body,
        "tags": [work, "ドキュメンタリー", "歴史", "宗教改革", "キリスト教"],
        "hashtags": ["#ドキュメンタリー", "#歴史", f"#{work}"],
        "pinned_comment": "この動画についてどう感じましたか？コメントで教えてください。",
        "thumbnail_text": chapter[:10],
    }


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────
def generate(scene_path: str, work: str, brief: str,
             keywords: list, privacy: str, thumbnail: str | None) -> dict:
    scenes = json.loads(Path(scene_path).read_text())
    analysis = analyze_scenes(scenes)
    chapter_name = Path(scene_path).stem

    prompt = _build_prompt(work, chapter_name, brief,
                           analysis["onscreen_texts"], keywords)
    raw = _call_groq(prompt)
    if raw:
        try:
            ai = json.loads(raw)
            print(f"  [gen_metadata] Groq生成成功: {ai.get('title','')[:40]}")
        except json.JSONDecodeError:
            print("  [gen_metadata] JSON解析失敗 → フォールバック")
            ai = _fallback(work, chapter_name, analysis["onscreen_texts"])
    else:
        ai = _fallback(work, chapter_name, analysis["onscreen_texts"])

    description = compose_description(
        ai.get("description_body", ""), analysis["chapters_block"],
        ai.get("hashtags", []), work)

    meta = {
        "title": ai["title"],
        "description": description,
        "tags": ai.get("tags", []),
        "category_id": CATEGORY_EDUCATION,
        "privacy": privacy,
        # 補助情報（upload_youtube.pyは無視するが運用で使う）
        "_title_alternatives": ai.get("title_alternatives", []),
        "_pinned_comment": ai.get("pinned_comment", ""),
        "_thumbnail_text": ai.get("thumbnail_text", ""),
        "_total_sec": round(analysis["total_sec"], 1),
    }
    if thumbnail:
        meta["thumbnail"] = thumbnail
    return meta


def main():
    ap = argparse.ArgumentParser(description="YouTubeメタデータ自動生成")
    ap.add_argument("scene_json", help="章のシーンJSON（scenes/ch6.json）")
    ap.add_argument("--work", default="勝利の福音", help="作品名")
    ap.add_argument("--brief", default=None, help="内容ブリーフのテキスト/MDファイル")
    ap.add_argument("--keywords", default="", help="狙うキーワード（カンマ区切り）")
    ap.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    ap.add_argument("--thumbnail", default=None, help="サムネイル画像パス")
    ap.add_argument("--out", default=None, help="出力先（省略時 scenes/<name>_meta.json）")
    args = ap.parse_args()

    if not Path(args.scene_json).exists():
        print(f"エラー: {args.scene_json} がありません")
        sys.exit(1)

    brief = ""
    if args.brief and Path(args.brief).exists():
        brief = Path(args.brief).read_text()
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    meta = generate(args.scene_json, args.work, brief, keywords,
                    args.privacy, args.thumbnail)

    out = args.out or str(BASE / "scenes" / f"{Path(args.scene_json).stem}_meta.json")
    Path(out).write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"\n生成完了: {out}")
    print(f"  タイトル: {meta['title']}")
    if meta.get("_title_alternatives"):
        for alt in meta["_title_alternatives"]:
            print(f"  代替案:   {alt}")


if __name__ == "__main__":
    main()

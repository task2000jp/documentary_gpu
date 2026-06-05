"""
research_engine.py — 論旨補完エンジン L1中核（ギャップ問い生成）

  python scripts/research_engine.py --auto 5
  python scripts/research_engine.py --phenomena "ブリティッシュロック,ハリウッド,シリコンバレー"

作品の論旨に対する「知識ギャップ」を、Groq(llama-3.3-70b)で問い化する。
各ギャップ = 事象 + 「成功の必然性」の問い + 「改革との相関」の問い + 初期仮説 + 統合先。
出力JSONは Sheets「論旨ギャップ」キューへ（Claude/GASが投入）。

深い調査・合成は L2(Claude+WebSearch) / L3(deep-research) が担う。本スクリプトは"問いを立てる"層。
設計根拠: docs/research_system.md
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
GROQ_MODEL = "llama-3.3-70b-versatile"

# 作品論旨の蒸留（問いの妥当性判定の軸）
THESIS = """作品「勝利の福音」の核心論旨:
福音→心の解放(Christus Victor)→宗教改革→科学/医療/経済の解放→産業革命
→メディア革命(録音/映像/放送)→IT/AI。
芸術(音楽/映画)は福音が建てたインフラに後乗りした「ペイロード(積載物)」。
本作自身もその構造の最新例(福音インフラに福音を再積載するペイロード)。"""


def _call_groq(prompt: str) -> str | None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("  GROQ_API_KEY未設定")
        return None
    payload = json.dumps({
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.85,
        "max_tokens": 3000,
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(
        GROQ_URL, data=payload,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json",
                 "User-Agent": "documentary-gpu/1.0"})  # Cloudflare 1010回避
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        print(f"  Groq HTTPエラー {e.code}: {e.read()[:200]}")
    except Exception as e:
        print(f"  Groqエラー: {e}")
    return None


def _prompt(phenomena: list[str] | None, auto_n: int) -> str:
    if phenomena:
        target = ("次の事象それぞれについて1件ずつギャップを作れ:\n"
                  + "\n".join(f"- {p}" for p in phenomena))
    else:
        target = (f"作品論旨を補完するうえで「成功の必然性が自明視されがちだが"
                  f"実は深く理解されていない事象」を{auto_n}個、自分で選んで作れ。"
                  f"文化・経済・科学・技術・宗教史から多様に。")

    return f"""あなたは知的ドキュメンタリーの首席リサーチャー。
{THESIS}

この論旨を洗練・完成させるため、「知識ギャップを埋める問い」を生成する。
良い問いのテンプレ:
「[事象X]はなぜ成功し資源(富/影響)を集めたのか(成功の必然性)。
 それは福音→解放→インフラ→ペイロードの論旨とどう関係・相関するか。」

{target}

各ギャップに必ず含める:
- domain: 領域(文化経済/科学/宗教史/技術 等)
- phenomenon: 事象名
- q_success: 「成功の必然性」を問う一文
- q_link: 「改革/論旨との相関」を問う一文
- hypothesis: 一次仮説(2〜3文。断定せず方向性。対抗仮説の余地も示す)
- counter: 論旨を弱めうる対抗仮説/反証の候補を一言(誠実さのため)
- integration_target: content_designのどの章/節に効くか
- priority: high|medium|low

必ず次のJSON形式のみ:
{{"gaps":[{{"domain":"...","phenomenon":"...","q_success":"...","q_link":"...","hypothesis":"...","counter":"...","integration_target":"...","priority":"high"}}]}}"""


def generate(phenomena=None, auto_n=5) -> list[dict]:
    raw = _call_groq(_prompt(phenomena, auto_n))
    if not raw:
        return []
    try:
        return json.loads(raw).get("gaps", [])
    except json.JSONDecodeError:
        print("  JSON解析失敗")
        return []


def main():
    ap = argparse.ArgumentParser(description="論旨ギャップ問いの生成(L1)")
    ap.add_argument("--phenomena", default="", help="事象（カンマ区切り）")
    ap.add_argument("--auto", type=int, default=5, help="自動で事象を選ぶ件数")
    ap.add_argument("--out", default=None, help="出力JSON（省略時 build/research/gaps.json）")
    args = ap.parse_args()

    phenomena = [p.strip() for p in args.phenomena.split(",") if p.strip()]
    gaps = generate(phenomena or None, args.auto)
    if not gaps:
        print("生成0件"); sys.exit(1)

    out = args.out or str(BASE / "build" / "research" / "gaps.json")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(gaps, ensure_ascii=False, indent=2))

    print(f"生成 {len(gaps)}件 → {out}\n")
    for g in gaps:
        print(f"[{g.get('priority','?'):6}] {g.get('phenomenon','?')} ({g.get('domain','?')})")
        print(f"  必然性: {g.get('q_success','')}")
        print(f"  相関  : {g.get('q_link','')}")
        print(f"  仮説  : {g.get('hypothesis','')[:120]}")
        print(f"  →統合 : {g.get('integration_target','')}\n")


if __name__ == "__main__":
    main()

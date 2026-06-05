"""
research_engine.py — 論旨補完エンジン L1中核（偏りなき・二軸ギャップ問い生成）

  python scripts/research_engine.py --mode mixed --n 6
  python scripts/research_engine.py --mode everyday --n 4
  python scripts/research_engine.py --phenomena "葬送のフリーレン,YOASOBI"

各ギャップ = 事象 + 成功次元 + 視点 + 3つの問い(機序/マクロ相関/被造設計) + 仮説 + 対抗仮説。
- 偏らせない: 成功を富だけに限定せず シャローム5次元で。対象はtrend/everyday/relational/random/elite混合。
- 全ては繋がる: マクロ(歴史/インフラ/摂理)＋ミクロ(脳/心の被造設計)の二軸で連関を"発見"。

深い調査はL2(Claude+WebSearch / research-specialist脳科学) / L3(deep-research)。本層は"問いを立てる"。
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

THESIS = """作品「勝利の福音」の論旨と世界観:
福音→心の解放(Christus Victor)→宗教改革→科学/医療/経済→産業革命→メディア革命→IT/AI。
芸術は福音インフラに乗ったペイロード。本作自身もその最新例。
【最重要の前提】成功は富だけではない。シャローム5次元(外の豊かさ/関係/健康/心の平和/神との和解)。
全ては繋がる—神=クリエイターが人間・脳・被造世界を作ったから。連関は捏造でなく発見する。"""

MODE_GUIDE = {
    "trend": "今ホットな事象(配信/急上昇/チャート/話題のアニメ・音楽・ゲーム)から選べ",
    "everyday": "大衆の日常消費(人気アニメ・流行曲・ゲーム・SNS)から選べ。エリートでなく庶民視点",
    "relational": "関係性・人物の成功(なぜ愛される/モテる/人望がある/幸福か)から選べ。富でない成功",
    "random": "領域を意図的にばらけさせ、偶然性のある多様な事象を選べ",
    "elite": "政治経済エリートの事象(企業/技術/覇権)。※既知が多いので低優先で",
    "mixed": "trend/everyday/relational/random/eliteを均衡配合し、成功次元も外的に偏らせるな",
}


def _call_groq(prompt: str) -> str | None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("  GROQ_API_KEY未設定"); return None
    payload = json.dumps({
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9, "max_tokens": 3500,
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


def _prompt(phenomena, mode, n) -> str:
    if phenomena:
        target = "次の事象それぞれ1件:\n" + "\n".join(f"- {p}" for p in phenomena)
    else:
        target = f"{MODE_GUIDE.get(mode, MODE_GUIDE['mixed'])}。{n}個作れ。"

    return f"""あなたは知的ドキュメンタリーの首席リサーチャー兼 認知/脳科学の素養を持つ分析者。
{THESIS}

「知識ギャップを埋める問い」を生成する。対象を偏らせるな（富/エリートに寄せない）。
各事象を**二軸**で問う:
- マクロ相関: 歴史・インフラ・摂理（福音→改革→産業→メディア→ペイロード）とどう繋がるか
- ミクロ相関（被造設計）: なぜ人間の脳・心は**それに惹かれるよう作られている**か
  （美・物語・愛着・社会的地位・帰属・超越への神経/心理的配線）

{target}

各ギャップに必ず:
- domain: 領域
- phenomenon: 事象名（具体的に。例「葬送のフリーレン」「YOASOBI」「特定の人物像」）
- success_type: 外的|関係的|身体的|内面的|霊的（シャローム5次元のどれか）
- perspective: trend|everyday|relational|random|elite
- q_mechanism: 「なぜ成功・浸透したのか(機序)」の一文
- q_macro: マクロ相関を問う一文
- q_micro: 被造設計(脳/心)との相関を問う一文
- hypothesis: 一次仮説(2〜3文・断定せず方向性)
- counter: 対抗仮説/反証候補(一言・誠実さのため)
- integration_target: content_designのどの章/節・神学枠組みに効くか
- priority: high|medium|low

必ず次のJSON形式のみ:
{{"gaps":[{{"domain":"","phenomenon":"","success_type":"","perspective":"","q_mechanism":"","q_macro":"","q_micro":"","hypothesis":"","counter":"","integration_target":"","priority":""}}]}}"""


def generate(phenomena=None, mode="mixed", n=6) -> list[dict]:
    raw = _call_groq(_prompt(phenomena, mode, n))
    if not raw:
        return []
    try:
        return json.loads(raw).get("gaps", [])
    except json.JSONDecodeError:
        print("  JSON解析失敗"); return []


def main():
    ap = argparse.ArgumentParser(description="偏りなき二軸ギャップ問いの生成(L1)")
    ap.add_argument("--phenomena", default="", help="事象（カンマ区切り・指定時はmode無視）")
    ap.add_argument("--mode", default="mixed",
                    choices=list(MODE_GUIDE.keys()), help="対象の取り方（既定mixed）")
    ap.add_argument("--n", type=int, default=6, help="生成件数")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    phenomena = [p.strip() for p in args.phenomena.split(",") if p.strip()]
    gaps = generate(phenomena or None, args.mode, args.n)
    if not gaps:
        print("生成0件"); sys.exit(1)

    out = args.out or str(BASE / "build" / "research" / "gaps.json")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(gaps, ensure_ascii=False, indent=2))

    # 偏り監視: 成功次元の分布
    from collections import Counter
    dist = Counter(g.get("success_type", "?") for g in gaps)
    print(f"生成 {len(gaps)}件 → {out}")
    print(f"成功次元の分布: {dict(dist)}\n")
    for g in gaps:
        print(f"[{g.get('priority','?'):6}|{g.get('success_type','?')}|{g.get('perspective','?')}] "
              f"{g.get('phenomenon','?')}")
        print(f"  機序  : {g.get('q_mechanism','')}")
        print(f"  マクロ: {g.get('q_macro','')}")
        print(f"  被造  : {g.get('q_micro','')}")
        print(f"  仮説  : {g.get('hypothesis','')[:110]}")
        print(f"  →統合 : {g.get('integration_target','')}\n")


if __name__ == "__main__":
    main()

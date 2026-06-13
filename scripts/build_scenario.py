"""
build_scenario.py — シナリオ(章の設計) → scenes JSON(絵コンテ) コンパイラ

「シナリオをレンダリングする機構」の中核。中身(どのシナリオ)に依存せず、
beat列を renderer が食える scenes/<章>.json へ変換する。純Python・torch不要で
ローカルでもColabでも動く（描画だけがColab）。

入力: scenarios/<章>.json
  {
    "chapter": "ch_demo",
    "defaults": { "grade": "warm", "style": "cinematic", "voice_wps": 7.0 },
    "music": "cues/knopfler_anthem.json",   // 任意。BGM cue（pipeline.py music で焼く）
    "beats": [
      { "id":"t", "kind":"title",  "text":"第一章", "colors":["#1a0a0a","#3a1a1a"] },
      { "id":"a", "kind":"prompt", "prompt":"wide factory ...", "style":"cinematic",
        "motion":"pan_lr", "text":"字幕", "narration":"読み上げ原稿...", "grade":"cold",
        "graphics":[ ... ] },
      { "id":"img","kind":"image", "image":"john_calvin.jpg", "motion":"orbit", "text":"..." },
      { "id":"h", "kind":"manim",  "scene":"AdapterSpine", "duration":10, "text":"背骨は不変" },
      { "id":"v", "kind":"video",  "prompt":"steam engine turning", "duration":5 }
    ]
  }

出力: scenes/<章>.json（renderer.render_chapter がそのまま描画）

声(ナレーション)は未構築でも止まらない:
  narration がある beat には audio パス build/audio/<id>.wav を先回りで配線する。
  そのwavが存在しない間は renderer が無音で描画し、後でwavを置けば自動でmuxされる。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent

# 章レベルのデフォルト（beat / scenario.defaults で上書き可）
CHAPTER_DEFAULTS = dict(
    grade="warm", style="cinematic", voice_wps=7.0,
    vignette=0.38, grain=0.03, fade_in=0.5, fade_out=0.5,
    amplitude=0.04, atmosphere=0.0,
)
VALID_KINDS = {"title", "gradient", "image", "prompt", "manim", "video"}
MIN_DUR, DEFAULT_DUR, TITLE_DUR, PAD = 3.0, 6.0, 4.0, 0.8


def _estimate_duration(beat: dict, wps: float) -> float:
    """尺の決定: 明示 > ナレーション長から推定 > 種別デフォルト。"""
    if beat.get("duration") is not None:
        return float(beat["duration"])
    narration = beat.get("narration")
    if narration:
        return max(MIN_DUR, round(len(narration) / max(1.0, wps) + PAD, 1))
    return TITLE_DUR if beat.get("kind") in ("title", "gradient") else DEFAULT_DUR


def _background(beat: dict, d: dict) -> dict:
    """beat.kind → renderer の background dict。"""
    kind = beat.get("kind", "prompt")
    motion = beat.get("motion", "orbit")
    amp = beat.get("amplitude", d["amplitude"])
    if kind in ("title", "gradient"):
        return {"type": "gradient", "colors": beat.get("colors", ["#0a0a12", "#15152e"])}
    if kind == "image":
        bg = {"type": "image", "path": f"assets/images/{beat['image']}",
              "motion": motion, "amplitude": amp}
        return bg
    if kind == "prompt":
        bg = {"type": "sd_generated", "prompt": beat["prompt"],
              "style": beat.get("style", d["style"]), "cache_key": beat["id"],
              "motion": motion, "amplitude": amp}
        if beat.get("negative"):
            bg["negative"] = beat["negative"]
        return bg
    if kind == "manim":
        bg = {"type": "manim", "scene": beat["scene"]}
        if beat.get("fallback"):
            bg["fallback"] = beat["fallback"]
        return bg
    if kind == "video":
        return {"type": "video_generated", "prompt": beat["prompt"]}
    raise ValueError(f"未知の kind: {kind}")


def compile_scenario(scenario: dict) -> list[dict]:
    """シナリオdict → scenes(list[dict])。"""
    d = {**CHAPTER_DEFAULTS, **(scenario.get("defaults") or {})}
    wps = float(d["voice_wps"])
    scenes: list[dict] = []
    for beat in scenario.get("beats", []):
        dur = _estimate_duration(beat, wps)
        scene = {
            "id": beat["id"],
            "duration": dur,
            "background": _background(beat, d),
            "grade": beat.get("grade", "sepia" if beat.get("kind") in ("title", "gradient") else d["grade"]),
            "vignette": beat.get("vignette", d["vignette"]),
            "grain": beat.get("grain", d["grain"]),
            "atmosphere": beat.get("atmosphere", d["atmosphere"]),
            "fade_in": beat.get("fade_in", d["fade_in"]),
            "fade_out": beat.get("fade_out", d["fade_out"]),
        }
        if beat.get("text"):
            scene["text"] = {"content": beat["text"],
                             "style": beat.get("text_style",
                                                "title" if beat.get("kind") in ("title", "gradient") else "subtitle")}
        if beat.get("graphics"):
            scene["graphics"] = beat["graphics"]
        # 声の配線（未構築でも止めない：wavが在る時だけ後でmuxされる）
        if beat.get("narration"):
            scene["audio"] = f"build/audio/{beat['id']}.wav"
        scenes.append(scene)
    return scenes


def validate_structure(scenario: dict) -> tuple[list[str], list[str]]:
    """コンパイル前の構造検証（必須フィールド等）。(errors, warnings)。"""
    errors, warnings = [], []
    if not scenario.get("chapter"):
        errors.append("chapter 名がありません")
    if not scenario.get("beats"):
        errors.append("beats が空です")
    seen = set()
    for i, beat in enumerate(scenario.get("beats", [])):
        tag = beat.get("id", f"#{i}")
        if not beat.get("id"):
            errors.append(f"beat {tag}: id がありません")
        elif beat["id"] in seen:
            errors.append(f"beat {tag}: id が重複")
        seen.add(beat.get("id"))
        kind = beat.get("kind", "prompt")
        if kind not in VALID_KINDS:
            errors.append(f"beat {tag}: 未知の kind '{kind}'")
        if kind == "prompt" and not beat.get("prompt"):
            errors.append(f"beat {tag}: prompt が必要")
        if kind == "image" and not beat.get("image"):
            errors.append(f"beat {tag}: image(ファイル名) が必要")
        if kind == "manim" and not beat.get("scene"):
            errors.append(f"beat {tag}: scene(Manimクラス名) が必要")
        if kind == "video" and not beat.get("prompt"):
            errors.append(f"beat {tag}: prompt が必要")
        if kind in ("title", "gradient") and not beat.get("colors"):
            warnings.append(f"beat {tag}: colors 未指定→既定の暗色グラデを使用")
    return errors, warnings


def validate_scenes(scenes: list[dict]) -> tuple[list[str], list[str]]:
    """コンパイル後の尺の健全性検証（v3.1教訓）。(errors, warnings)。"""
    errors, warnings = [], []
    for sc in scenes:
        if sc["duration"] < 1.0:
            errors.append(f"scene {sc['id']}: duration {sc['duration']}s が短すぎ")
        g = sc.get("graphics") or []
        appear = [x for x in g if x.get("appear") or x.get("draw")]
        if appear and sc["duration"] < 2.0:
            warnings.append(f"scene {sc['id']}: graphics に対し尺{sc['duration']}sが短い恐れ")
    return errors, warnings


def load_scenario(arg: str) -> dict:
    """scenarios/<名>.json か 直接パスを読む。"""
    p = Path(arg)
    if not p.exists():
        cand = BASE / "scenarios" / f"{arg}.json"
        if cand.exists():
            p = cand
        else:
            raise FileNotFoundError(f"シナリオが見つかりません: {arg}（scenarios/{arg}.json も無し）")
    return json.loads(p.read_text())


def build(arg: str, out: str | None = None) -> tuple[str, list[dict]]:
    """シナリオ → scenes/<章>.json を書き出し、(path, scenes) を返す。"""
    scenario = load_scenario(arg)
    # ① 構造検証（コンパイル前。必須フィールド欠落をここで止める）
    errors, warnings = validate_structure(scenario)
    # ② コンパイル（構造OKのbeatのみ安全に変換）
    scenes = compile_scenario(scenario) if not errors else []
    # ③ 尺の健全性検証
    if scenes:
        e2, w2 = validate_scenes(scenes)
        errors += e2
        warnings += w2
    for w in warnings:
        print(f"  ⚠️  {w}")
    if errors:
        for e in errors:
            print(f"  ❌ {e}")
        raise ValueError(f"{len(errors)}件のエラーで中断")
    chapter = scenario["chapter"]
    out_path = out or str(BASE / "scenes" / f"{chapter}.json")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(scenes, ensure_ascii=False, indent=2))
    total = round(sum(s["duration"] for s in scenes), 1)
    print(f"  ✅ {chapter}: {len(scenes)}シーン / 計{total}秒 → {out_path}")
    if scenario.get("music"):
        print(f"  🎵 BGM: {scenario['music']}（python scripts/pipeline.py music ... で別途）")
    return out_path, scenes


def main():
    import argparse
    ap = argparse.ArgumentParser(description="シナリオ → scenes JSON コンパイラ")
    ap.add_argument("scenario", help="scenarios/<名>.json か JSONパス")
    ap.add_argument("--out", default=None, help="出力 scenes JSON")
    args = ap.parse_args()
    build(args.scenario, args.out)


if __name__ == "__main__":
    main()

"""
make_scenes.py — 台本（アウトライン）→ シーン定義JSON 変換
前プロジェクトの script_proto.py 的なセグメント列を scenes/*.json に変換する土台。

入力（outline）フォーマット例（YAML風の簡易タプル list）:
    seg_id, image_or_prompt, motion, text, grade
を Python で定義 → このスクリプトで JSON 化。

実運用では:
  1. Claude が台本テキストからこの outline を生成
  2. narration.synthesize() で各 seg_id の音声を作り duration を measure()
  3. ここで scene JSON を書き出す
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "src"))

DEFAULTS = dict(grade="warm", vignette=0.38, grain=0.03,
                fade_in=0.5, fade_out=0.5, amplitude=0.04)


def build_scene(seg_id, source, motion, text, *,
                is_prompt=False, style="cinematic", duration=None,
                grade=None, atmosphere=0.0):
    """1シーン分の dict を組み立てる。"""
    if is_prompt:
        bg = {"type": "sd_generated", "prompt": source, "style": style,
              "cache_key": seg_id, "motion": motion, "amplitude": DEFAULTS["amplitude"]}
    else:
        bg = {"type": "image", "path": f"assets/images/{source}",
              "motion": motion, "amplitude": DEFAULTS["amplitude"]}

    # duration 未指定なら音声長から決定（音声が無ければ 6 秒）
    if duration is None:
        try:
            import narration
            duration = round(narration.measure(seg_id) + 0.5, 2)
        except Exception:
            duration = 6.0

    scene = {
        "id": seg_id,
        "duration": duration,
        "background": bg,
        "audio": f"build/audio/{seg_id}.wav",
        "grade": grade or DEFAULTS["grade"],
        "vignette": DEFAULTS["vignette"],
        "grain": DEFAULTS["grain"],
        "atmosphere": atmosphere,
        "fade_in": DEFAULTS["fade_in"],
        "fade_out": DEFAULTS["fade_out"],
    }
    if text:
        scene["text"] = {"content": text, "style": "subtitle"}
    return scene


def write_chapter(name: str, scenes: list):
    out = BASE / "scenes" / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scenes, ensure_ascii=False, indent=2))
    print(f"書き出し: {out}（{len(scenes)}シーン）")


if __name__ == "__main__":
    # デモ: アウトライン → ch_demo.json
    outline = [
        ("demo_title", "#1a0a0a/#3a1a1a", "gradient", "第六章　宗教改革", "title"),
        ("demo_door", "luther_wittenberg.jpg", "dolly", "一五一七年十月三十一日", None),
        ("demo_calvin", "john_calvin.jpg", "orbit", "改革は広がった", None),
    ]
    scenes = []
    for seg_id, src, motion, text, kind in outline:
        if motion == "gradient":
            c1, c2 = src.split("/")
            scenes.append({"id": seg_id, "duration": 4.0,
                           "background": {"type": "gradient", "colors": [c1, c2]},
                           "text": {"content": text, "style": "title"},
                           "grade": "sepia", "vignette": 0.5, "grain": 0.04,
                           "fade_in": 0.8, "fade_out": 0.6})
        else:
            scenes.append(build_scene(seg_id, src, motion, text, duration=6.0))
    write_chapter("ch_demo", scenes)

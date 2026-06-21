"""
preview_render.py — torch不要の簡易アニマティック・レンダラ

本番(renderer.py)はFLUX/深度パララックス=torch=Colab。こちらは設計確認用に
ローカル(PIL/numpy/ffmpeg)だけで scenes/<章>.json を実mp4化する。
- 背景: gradient/title は色で、prompt/image/manim は「何が入るか」のプレースホルダ枠で描画。
- text(タイトル/字幕) と graphics(ノード/リンク/ラベル, appear/draw窓) を時間で動かす。
- 音声は付けない(劇伴wavはfluidsynth=Colab)。尺・構成・図解の確認用。

  python scripts/pipeline.py preview <章>     （または直接: python scripts/preview_render.py <章>）
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).parent.parent
W, H, FPS = 1280, 720, 12
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in _FONT_CANDIDATES:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _hex(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _gradient(colors) -> np.ndarray:
    c1 = np.array(_hex(colors[0]), float)
    c2 = np.array(_hex(colors[1] if len(colors) > 1 else colors[0]), float)
    t = np.linspace(0, 1, H).reshape(H, 1, 1)
    return (c1 * (1 - t) + c2 * t).repeat(W, axis=1).astype(np.uint8)


def _bg_array(scene: dict) -> tuple[np.ndarray, str]:
    """背景の下地(np)と、プレースホルダに出す説明文を返す。"""
    bg = scene.get("background", {})
    bt = bg.get("type", "gradient")
    if bt in ("gradient",):
        return _gradient(bg.get("colors", ["#0a0a12", "#15152e"])), ""
    if bt == "sd_generated":
        return _gradient(["#10131c", "#1c2330"]), "［FLUX画像］ " + (bg.get("prompt", "")[:60])
    if bt == "image":
        return _gradient(["#141414", "#202020"]), "［既存画像→パララックス］ " + bg.get("path", "")
    if bt == "manim":
        fb = bg.get("fallback", {}).get("colors", ["#06121f", "#0d3450"])
        return _gradient(fb), "［Manim: " + str(bg.get("scene", "")) + "］"
    if bt == "video_generated":
        return _gradient(["#0c0c0c", "#1a1a1a"]), "［LTX動画］ " + (bg.get("prompt", "")[:60])
    return _gradient(["#202020", "#101010"]), ""


def _alpha(window, t: float) -> float:
    """appear/draw 窓 [t0,t1] に対する 0..1 進捗。"""
    if not window:
        return 1.0
    t0, t1 = float(window[0]), float(window[1])
    if t <= t0:
        return 0.0
    if t >= t1:
        return 1.0
    return (t - t0) / max(1e-3, t1 - t0)


def _xy(at):
    return int(at[0] * W), int(at[1] * H)


def _draw_graphics(draw: ImageDraw.ImageDraw, graphics: list, t: float):
    for g in [x for x in graphics if x.get("type") == "link"]:
        prog = _alpha(g.get("draw") or g.get("appear"), t)
        if prog <= 0:
            continue
        x0, y0 = _xy(g["from"])
        x1, y1 = _xy(g["to"])
        ex = x0 + (x1 - x0) * prog
        ey = y0 + (y1 - y0) * prog
        col = tuple(g.get("color", [0, 200, 255]))
        draw.line([(x0, y0), (ex, ey)], fill=col, width=3)
        if g.get("arrow") and prog > 0.98:
            ang = math.atan2(ey - y0, ex - x0)
            for s in (-0.4, 0.4):
                draw.line([(ex, ey), (ex - 16 * math.cos(ang - s), ey - 16 * math.sin(ang - s))], fill=col, width=3)
        if g.get("flow"):
            fx = x0 + (x1 - x0) * ((t * 0.5) % 1.0)
            fy = y0 + (y1 - y0) * ((t * 0.5) % 1.0)
            draw.ellipse([fx - 5, fy - 5, fx + 5, fy + 5], fill=col)
        if g.get("label"):
            draw.text(((x0 + x1) / 2, (y0 + y1) / 2 - 18), g["label"], font=_font(22), fill=col, anchor="mm")
    for g in [x for x in graphics if x.get("type") == "node"]:
        a = _alpha(g.get("appear"), t)
        if a <= 0:
            continue
        cx, cy = _xy(g["at"])
        col = tuple(g.get("color", [0, 200, 255]))
        if g.get("shape") == "box":
            w = g.get("w", 0.12) * W / 2
            h = g.get("h", 0.12) * H / 2
            draw.rectangle([cx - w, cy - h, cx + w, cy + h], outline=col, width=3)
        else:
            r = g.get("r", 0.05) * H
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=3)
        if g.get("label"):
            draw.text((cx, cy), g["label"], font=_font(24), fill=col, anchor="mm")
    for g in [x for x in graphics if x.get("type") == "label"]:
        a = _alpha(g.get("appear"), t)
        if a <= 0:
            continue
        draw.text(_xy(g["at"]), g.get("text", ""), font=_font(g.get("size", 28)), fill=(255, 255, 255), anchor="mm")


def _draw_text(draw: ImageDraw.ImageDraw, text: dict):
    style = text.get("style", "subtitle")
    content = text.get("content", "")
    if style == "title":
        f = _font(64)
        y = H * 0.42
    elif style == "subtitle":
        f = _font(40)
        y = H * 0.80
    else:
        f = _font(32)
        y = H * 0.85
    for i, line in enumerate(content.split("\n")):
        yy = y + i * (f.size + 12)
        # 影
        draw.text((W / 2 + 2, yy + 2), line, font=f, fill=(0, 0, 0), anchor="mm")
        draw.text((W / 2, yy), line, font=f, fill=(245, 240, 235), anchor="mm")


def _frame(scene: dict, base: np.ndarray, placeholder: str, t: float, dur: float) -> bytes:
    # 微ズーム(ケンバーンズ)
    zoom = 1.0 + 0.05 * (t / max(dur, 0.1))
    img = Image.fromarray(base)
    zw, zh = int(W * zoom), int(H * zoom)
    img = img.resize((zw, zh)).crop(((zw - W) // 2, (zh - H) // 2, (zw - W) // 2 + W, (zh - H) // 2 + H))
    draw = ImageDraw.Draw(img, "RGBA")
    if placeholder:
        draw.rectangle([W * 0.08, H * 0.08, W * 0.92, H * 0.30], outline=(120, 130, 150), width=2)
        draw.text((W * 0.10, H * 0.11), placeholder, font=_font(24), fill=(150, 165, 190))
    if scene.get("graphics"):
        _draw_graphics(draw, scene["graphics"], t)
    if scene.get("text"):
        _draw_text(draw, scene["text"])
    # フェード
    fi, fo = scene.get("fade_in", 0.0), scene.get("fade_out", 0.0)
    k = 1.0
    if fi and t < fi:
        k = t / fi
    if fo and t > dur - fo:
        k = min(k, (dur - t) / fo)
    arr = np.asarray(img).astype(np.float32)
    if k < 1.0:
        arr *= max(0.0, k)
    return arr.clip(0, 255).astype(np.uint8).tobytes()


def render(chapter: str, out: str | None = None) -> str:
    scenes_path = BASE / "scenes" / f"{chapter}.json"
    if not scenes_path.exists():
        raise FileNotFoundError(f"{scenes_path} がありません（先に pipeline.py scenario {chapter}）")
    scenes = json.loads(scenes_path.read_text())
    out = out or str(BASE / "build" / "preview" / f"{chapter}.mp4")
    Path(out).parent.mkdir(parents=True, exist_ok=True)

    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", out],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    total = 0.0
    for sc in scenes:
        dur = float(sc.get("duration", 5.0))
        base, placeholder = _bg_array(sc)
        for i in range(max(1, int(dur * FPS))):
            ff.stdin.write(_frame(sc, base, placeholder, i / FPS, dur))
        total += dur
    ff.stdin.close()
    ff.wait()
    print(f"  ✅ プレビュー: {len(scenes)}シーン / {round(total,1)}秒 → {out}")
    print("  ※ 簡易アニマティック(無音・背景はプレースホルダ)。本番画はColabで render。")
    return out


def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/preview_render.py <章>")
        return
    render(sys.argv[1])


if __name__ == "__main__":
    main()

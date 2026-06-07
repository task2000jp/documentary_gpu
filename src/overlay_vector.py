"""
overlay_vector.py — 図形・線・データ流のベクター描画層（精密・アニメ可）

compositor.render_text_rgba と同じ流儀で、各フレーム(時間 t)の図形を
RGBA tensor (4,H,W) に描いて重ねる。FLUX実写背景の上に、精密な接続図
（ノード=設備/背骨、線=アダプタ/API、流れる光点=データ、矢印=制御）を載せる。

設計原則「設計＋精密描画 ≫ ランダム生成」(CLAUDE.md) の実装。追加依存なし。
描画は 2x スーパーサンプリング → 縮小でアンチエイリアス。

scene の "graphics": [ {type, ...}, ... ] を受け取る。要素タイプ:
  node : {at:[x,y], shape:"circle"|"box", r, w, h, label, color, appear:[t0,t1], pulse}
  link : {from:[x,y], to:[x,y], width, color, draw:[t0,t1], flow, arrow, label}
  label: {at:[x,y], text, size, color, appear:[t0,t1]}
座標・寸法は 0..1 正規化（x=画面幅, y=画面高, r=高さ基準, box w/h=幅/高基準）。
appear=フェードイン窓 / draw=線が伸びる窓 / flow=線上を光点が流れる / pulse=脈動。
"""
import math
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
S = 2  # スーパーサンプリング倍率（アンチエイリアス）
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

FONT_PATHS = [
    "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]
CYAN = (0, 200, 255)
WHITE = (240, 248, 255)
AMBER = (255, 200, 90)

_font_cache: dict = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    key = int(size)
    if key in _font_cache:
        return _font_cache[key]
    for p in FONT_PATHS:
        if Path(p).exists():
            f = ImageFont.truetype(p, key)
            _font_cache[key] = f
            return f
    f = ImageFont.load_default()
    _font_cache[key] = f
    return f


# ── 座標・時間ヘルパー（全て SS 空間に変換）──
def _px(pt):
    return (pt[0] * W * S, pt[1] * H * S)


def _alpha(g: dict, t: float) -> float:
    ap = g.get("appear")
    if not ap:
        return 1.0
    t0, t1 = ap
    if t <= t0:
        return 0.0
    if t >= t1:
        return 1.0
    return (t - t0) / (t1 - t0)


def _progress(g: dict, t: float) -> float:
    dr = g.get("draw")
    if not dr:
        return 1.0
    t0, t1 = dr
    if t <= t0:
        return 0.0
    if t >= t1:
        return 1.0
    return (t - t0) / (t1 - t0)


def _dark(color):
    return tuple(int(c * 0.22) for c in color)


def _text(draw, s, cx, cy, size, alpha, color=WHITE, center=True):
    f = _font(int(size) * S)
    a = int(255 * alpha)
    bbox = draw.textbbox((0, 0), s, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = cx - tw / 2 if center else cx
    y = cy - th / 2
    draw.text((x + 2 * S, y + 2 * S), s, font=f, fill=(0, 0, 0, int(a * 0.7)))
    draw.text((x, y), s, font=f, fill=(*color, a))


# ── プリミティブ ──
def _draw_line(draw, p0, p1, color, width, alpha, prog):
    x0, y0 = _px(p0)
    x1, y1 = _px(p1)
    xe = x0 + (x1 - x0) * prog
    ye = y0 + (y1 - y0) * prog
    a = int(255 * alpha)
    w = max(1, int(width * S))
    draw.line([x0, y0, xe, ye], fill=(*color, int(a * 0.22)), width=w * 4)  # glow
    draw.line([x0, y0, xe, ye], fill=(*color, a), width=w)                  # core
    return (xe, ye)


def _arrowhead(draw, p0, p1, prog, color, alpha, size=16):
    x0, y0 = _px(p0)
    x1, y1 = _px(p1)
    xe = x0 + (x1 - x0) * prog
    ye = y0 + (y1 - y0) * prog
    ang = math.atan2(ye - y0, xe - x0)
    s = size * S
    a = int(255 * alpha)
    p_a = (xe, ye)
    p_b = (xe - s * math.cos(ang - 0.45), ye - s * math.sin(ang - 0.45))
    p_c = (xe - s * math.cos(ang + 0.45), ye - s * math.sin(ang + 0.45))
    draw.polygon([p_a, p_b, p_c], fill=(*color, a))


def _draw_flow(draw, p0, p1, t, prog, alpha, n=4, speed=0.45):
    x0, y0 = _px(p0)
    x1, y1 = _px(p1)
    phase = (t * speed) % (1.0 / n)
    a = int(255 * alpha)
    r = 6 * S
    for i in range(n):
        f = (i / n + phase) % 1.0
        if f > prog:
            continue
        x = x0 + (x1 - x0) * f
        y = y0 + (y1 - y0) * f
        draw.ellipse([x - r * 2, y - r * 2, x + r * 2, y + r * 2],
                     fill=(*WHITE, int(a * 0.30)))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*WHITE, a))


def _draw_link(draw, g, t):
    a = _alpha(g, t)
    if a <= 0:
        return
    prog = _progress(g, t)
    color = tuple(g.get("color", CYAN))
    p0, p1 = g["from"], g["to"]
    width = g.get("width", 5)
    _draw_line(draw, p0, p1, color, width, a, prog)
    if g.get("flow"):
        _draw_flow(draw, p0, p1, t, prog, a)
    if g.get("arrow"):
        _arrowhead(draw, p0, p1, prog, color, a)
    if g.get("label") and prog > 0.15:
        mx, my = (p0[0] + p1[0]) / 2 * W * S, (p0[1] + p1[1]) / 2 * H * S
        _text(draw, g["label"], mx, my - 30 * S, g.get("label_size", 28), a, color=WHITE)


def _draw_node(draw, g, t):
    a = _alpha(g, t)
    if a <= 0:
        return
    x, y = _px(g["at"])
    color = tuple(g.get("color", CYAN))
    ai = int(255 * a)
    pulse = 1.0 + 0.08 * math.sin(t * 3.0) if g.get("pulse") else 1.0

    if g.get("shape") == "box":
        bw = g.get("w", 0.17) * W * S * pulse
        bh = g.get("h", 0.13) * H * S * pulse
        box = [x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2]
        glow = [box[0] - 6 * S, box[1] - 6 * S, box[2] + 6 * S, box[3] + 6 * S]
        draw.rounded_rectangle(glow, radius=18 * S, outline=(*color, int(ai * 0.22)), width=10 * S)
        draw.rounded_rectangle(box, radius=14 * S, fill=(*_dark(color), int(ai * 0.6)),
                               outline=(*color, ai), width=4 * S)
        if g.get("label"):
            _text(draw, g["label"], x, y, g.get("label_size", 34), a, color=WHITE)
    else:
        r = g.get("r", 0.05) * H * S * pulse
        draw.ellipse([x - r * 1.25, y - r * 1.25, x + r * 1.25, y + r * 1.25],
                     outline=(*color, int(ai * 0.22)), width=10 * S)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*_dark(color), int(ai * 0.55)),
                     outline=(*color, ai), width=4 * S)
        if g.get("label"):
            _text(draw, g["label"], x, y + r + 30 * S, g.get("label_size", 30), a, color=WHITE)


def _draw_label(draw, g, t):
    a = _alpha(g, t)
    if a <= 0:
        return
    x, y = _px(g["at"])
    _text(draw, g["text"], x, y, g.get("size", 32), a,
          color=tuple(g.get("color", CYAN)))


# ── 公開API ──
def render_graphics_rgba(graphics: list, t: float, duration: float) -> torch.Tensor:
    """graphics 定義を時間 t で描画 → RGBA tensor (4,H,W) 0..1。"""
    img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    for g in graphics:  # 線が下、ノードが上、ラベルが最前
        if g.get("type") == "link":
            _draw_link(draw, g, t)
    for g in graphics:
        if g.get("type") == "node":
            _draw_node(draw, g, t)
    for g in graphics:
        if g.get("type") == "label":
            _draw_label(draw, g, t)
    img = img.resize((W, H), Image.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0
    return torch.from_numpy(arr).permute(2, 0, 1).to(DEVICE)

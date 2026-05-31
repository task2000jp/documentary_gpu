"""
compositor.py — GPU後処理（シネマ質感の核）
パララックスクリップに「映画的な仕上げ」を重ねる:
  カラーグレード / ビネット / フィルムグレイン / 大気粒子 / テキスト / フェード
全てテンソル演算で高速に。
"""
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

W, H = 1920, 1080
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

FONT_PATHS = [
    "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]
TEXT_STYLES = {
    "title":    {"size": 80, "color": (255, 255, 255), "y": "center"},
    "subtitle": {"size": 50, "color": (245, 245, 235), "y": "bottom"},
    "caption":  {"size": 36, "color": (210, 210, 210), "y": "bottom"},
    "quote":    {"size": 46, "color": (255, 238, 180), "y": "center"},
}

# ─── カラーグレードのプリセット（lift, gamma, gain 風の簡易トーン）───
GRADE_PRESETS = {
    "warm":   {"mul": (1.08, 1.00, 0.90), "lift": (0.02, 0.01, 0.00)},
    "cold":   {"mul": (0.92, 0.98, 1.10), "lift": (0.00, 0.01, 0.03)},
    "sepia":  {"mul": (1.10, 0.95, 0.75), "lift": (0.03, 0.02, 0.00)},
    "neutral":{"mul": (1.00, 1.00, 1.00), "lift": (0.00, 0.00, 0.00)},
}

_vignette_cache = None


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_PATHS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def color_grade(frame: torch.Tensor, preset: str = "neutral") -> torch.Tensor:
    """frame (3,H,W) 0..1 にカラーグレードを適用。"""
    g = GRADE_PRESETS.get(preset, GRADE_PRESETS["neutral"])
    mul = torch.tensor(g["mul"], device=frame.device).view(3, 1, 1)
    lift = torch.tensor(g["lift"], device=frame.device).view(3, 1, 1)
    return (frame * mul + lift).clamp(0, 1)


def vignette(frame: torch.Tensor, strength: float = 0.35) -> torch.Tensor:
    """周辺減光。中心を明るく、周辺を暗く。"""
    global _vignette_cache
    if _vignette_cache is None:
        ys, xs = torch.meshgrid(
            torch.linspace(-1, 1, H, device=frame.device),
            torch.linspace(-1, 1, W, device=frame.device),
            indexing="ij")
        r = torch.sqrt(xs ** 2 + ys ** 2) / 1.414
        _vignette_cache = (1 - r ** 2).clamp(0, 1)
    mask = 1 - strength * (1 - _vignette_cache)
    return (frame * mask.unsqueeze(0)).clamp(0, 1)


def film_grain(frame: torch.Tensor, amount: float = 0.03) -> torch.Tensor:
    """フィルムグレイン（微細ノイズ）。"""
    noise = torch.randn_like(frame) * amount
    return (frame + noise).clamp(0, 1)


def atmosphere(frame: torch.Tensor, particles: torch.Tensor = None,
               intensity: float = 0.0) -> torch.Tensor:
    """大気粒子（埃・光の粒）の薄い重ね。intensity=0 ならスキップ。"""
    if intensity <= 0 or particles is None:
        return frame
    return (frame + particles * intensity).clamp(0, 1)


def make_particle_field(n: int = 400) -> torch.Tensor:
    """ランダムな光の粒フィールド (3,H,W) を生成（atmosphere用）。"""
    field = torch.zeros(3, H, W, device=DEVICE)
    ys = torch.randint(0, H, (n,))
    xs = torch.randint(0, W, (n,))
    field[:, ys, xs] = torch.rand(n, device=DEVICE) * 0.8 + 0.2
    # 軽くぼかす
    k = torch.ones(1, 1, 3, 3, device=DEVICE) / 9
    field = F.conv2d(field.unsqueeze(1), k, padding=1).squeeze(1)
    return field


def render_text_rgba(content: str, style: str = "subtitle") -> torch.Tensor:
    """テキストを RGBA tensor (4,H,W) 0..1 に描画（PIL→GPU）。"""
    cfg = TEXT_STYLES.get(style, TEXT_STYLES["subtitle"])
    font = _font(cfg["size"])
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), content, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (W - tw) // 2
    y = {"center": (H - th) // 2, "bottom": H - th - 90, "top": 90}[cfg["y"]]
    draw.text((x + 3, y + 3), content, font=font, fill=(0, 0, 0, 170))  # shadow
    draw.text((x, y), content, font=font, fill=(*cfg["color"], 255))
    arr = np.array(img, dtype=np.float32) / 255.0
    return torch.from_numpy(arr).permute(2, 0, 1).to(DEVICE)


def overlay_text(frame: torch.Tensor, text_rgba: torch.Tensor,
                 alpha: float = 1.0) -> torch.Tensor:
    """frame(3,H,W) に text_rgba(4,H,W) を合成。alphaでフェード制御。"""
    rgb = text_rgba[:3]
    a = text_rgba[3:4] * alpha
    return (frame * (1 - a) + rgb * a).clamp(0, 1)


def fade(frame: torch.Tensor, t: float, duration: float,
         fade_in: float = 0.5, fade_out: float = 0.5) -> torch.Tensor:
    """シーン内 t 秒でのフェード係数を適用。"""
    a = 1.0
    if t < fade_in:
        a = t / fade_in
    elif t > duration - fade_out:
        a = max(0.0, (duration - t) / fade_out)
    return frame * a

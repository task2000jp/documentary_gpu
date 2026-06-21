"""
renderer.py — クリップベース統括レンダラー
各シーン: ベース動きクリップ生成 → GPU後処理 → 音声結合。最後に全シーン結合。

ベースクリップの種類:
  - parallax : depth_parallax（深度→立体カメラ移動）★標準
  - title    : GPU生成グラデーション
  - video    : video_gen（LTX-Video、hero shotのみ）
"""
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import torch
from PIL import Image

import compositor as comp
import depth_parallax as dp
import overlay_vector as ov

W, H, FPS = 1920, 1080, 24
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
BUILD = Path(__file__).parent.parent / "build"
FRAME_BYTES = W * H * 3


# ─────────────────────────────────────────────
# ffmpeg 入出力パイプ
# ─────────────────────────────────────────────
def _decode_pipe(clip: str) -> subprocess.Popen:
    """既存クリップを raw rgb24 で読み出すパイプ。"""
    cmd = ["ffmpeg", "-i", clip, "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-"]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)


def _encode_pipe(out: str) -> subprocess.Popen:
    """raw rgb24 を受けて mp4 にエンコードするパイプ。"""
    codec = "h264_nvenc" if DEVICE.type == "cuda" else "libx264"
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
           "-s", f"{W}x{H}", "-pix_fmt", "rgb24", "-r", str(FPS), "-i", "-",
           "-c:v", codec, "-preset", "p4" if codec == "h264_nvenc" else "fast",
           "-pix_fmt", "yuv420p", out]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)


# ─────────────────────────────────────────────
# ベースクリップ生成
# ─────────────────────────────────────────────
def _base_clip(scene: dict, out: str) -> str:
    bg = scene.get("background", {})
    btype = bg.get("type", "parallax")
    duration = scene["duration"]

    if btype in ("parallax", "image", "sd_generated"):
        image = _resolve_image(bg)
        if btype == "sd_generated":
            import image_gen
            # FLUXのみVRAM解放（Depthと共存不可・T4 15GB）。SDXLはcpu_offloadで共存でき、
            # 毎シーン解放→再ロード(7GB)が遅延と無料RAM逼迫の主因なので保持する。
            if getattr(image_gen, "_backend", None) == "flux":
                image_gen.free()
        motion = bg.get("motion", "orbit")
        amp = bg.get("amplitude", 0.04)
        return dp.animate_parallax(image, out, duration=duration,
                                   motion=motion, amplitude=amp)
    if btype == "gradient":
        return _gradient_clip(bg, duration, out)
    if btype == "video_generated":
        import video_gen
        return video_gen.generate(bg["prompt"], out, duration=duration)
    if btype == "manim":
        import manim_render
        try:
            return manim_render.render(bg["scene"], out)
        except Exception as e:  # ハング(timeout)/失敗 → 章を止めずプレースホルダで継続
            print(f"  [manim] 失敗→グラデ代替: {type(e).__name__}: {e}")
            return _gradient_clip(bg.get("fallback", {"colors": ["#06121f", "#0d3450"]}),
                                  duration, out)
    # 不明 → グレーのプレースホルダ
    return _gradient_clip({"colors": ["#202020", "#101010"]}, duration, out)


def _resolve_image(bg: dict) -> Image.Image:
    """背景画像を取得（既存ファイル or AI生成）。"""
    if bg.get("type") == "sd_generated" or "prompt" in bg:
        import image_gen
        return image_gen.generate_background(
            bg["prompt"], style=bg.get("style", "cinematic"),
            cache_key=bg.get("cache_key"), negative=bg.get("negative"))
    path = bg["path"]
    if not Path(path).is_absolute():
        path = str(Path(__file__).parent.parent / path)
    return Image.open(path).convert("RGB")


def _gradient_clip(bg: dict, duration: float, out: str) -> str:
    """GPU生成のグラデーション背景（タイトル用）。"""
    c1, c2 = bg.get("colors", ["#0a0a2e", "#1a1a4e"])
    a = torch.tensor(_hex(c1), device=DEVICE).view(3, 1, 1) / 255
    b = torch.tensor(_hex(c2), device=DEVICE).view(3, 1, 1) / 255
    ys = torch.linspace(0, 1, H, device=DEVICE).view(1, H, 1)
    grad = (a * (1 - ys) + b * ys).expand(3, H, W).clone()

    proc = _encode_pipe(out)
    n = int(duration * FPS)
    try:
        for _ in range(n):
            frame = (grad.clamp(0, 1) * 255).byte().permute(1, 2, 0).contiguous()
            proc.stdin.write(frame.cpu().numpy().tobytes())
    finally:
        proc.stdin.close()
        proc.wait()
    return out


def _hex(h: str):
    h = h.lstrip("#")
    return [int(h[i:i+2], 16) for i in (0, 2, 4)]


# ─────────────────────────────────────────────
# 後処理パス（grade/grain/vignette/text/fade）
# ─────────────────────────────────────────────
def _postprocess(in_clip: str, out_clip: str, scene: dict):
    duration = scene["duration"]
    grade = scene.get("grade", "neutral")
    grain = scene.get("grain", 0.03)
    vig = scene.get("vignette", 0.35)
    atmos = scene.get("atmosphere", 0.0)
    text_cfg = scene.get("text")
    graphics = scene.get("graphics")

    text_rgba = None
    if text_cfg:
        text_rgba = comp.render_text_rgba(text_cfg["content"],
                                          text_cfg.get("style", "subtitle"))
    particles = comp.make_particle_field() if atmos > 0 else None

    dec = _decode_pipe(in_clip)
    enc = _encode_pipe(out_clip)
    i = 0
    try:
        while True:
            raw = dec.stdout.read(FRAME_BYTES)
            if len(raw) < FRAME_BYTES:
                break
            t = i / FPS
            arr = np.frombuffer(raw, np.uint8).reshape(H, W, 3)
            frame = torch.from_numpy(arr.copy()).permute(2, 0, 1).float().to(DEVICE) / 255

            frame = comp.color_grade(frame, grade)
            frame = comp.vignette(frame, vig)
            frame = comp.atmosphere(frame, particles, atmos)
            frame = comp.film_grain(frame, grain)
            if graphics:  # ベクター図解層（線/ノード/データ流）を実写の上に
                g_rgba = ov.render_graphics_rgba(graphics, t, duration)
                frame = comp.overlay_text(frame, g_rgba)
            if text_rgba is not None:
                frame = comp.overlay_text(frame, text_rgba)
            frame = comp.fade(frame, t, duration,
                              scene.get("fade_in", 0.5), scene.get("fade_out", 0.5))

            out = (frame.clamp(0, 1) * 255).byte().permute(1, 2, 0).contiguous()
            enc.stdin.write(out.cpu().numpy().tobytes())
            i += 1
    finally:
        enc.stdin.close()
        enc.wait()
        dec.wait()


# ─────────────────────────────────────────────
# 音声結合・シーン・章
# ─────────────────────────────────────────────
def _mux_audio(clip: str, audio: str, out: str):
    """映像クリップに音声を結合（短い方に合わせる）。"""
    subprocess.run(["ffmpeg", "-y", "-i", clip, "-i", audio,
                    "-c:v", "copy", "-c:a", "aac", "-shortest", out],
                   stderr=subprocess.DEVNULL, check=True)


def render_scene(scene: dict, out_dir: Path) -> str:
    """1シーン → 最終クリップ（音声付き）。"""
    sid = scene["id"]
    tmp = Path(tempfile.mkdtemp())
    base = str(tmp / f"{sid}_base.mp4")
    post = str(tmp / f"{sid}_post.mp4")
    final = str(out_dir / f"{sid}.mp4")

    print(f"  [scene] {sid} ({scene['duration']:.1f}s)")
    _base_clip(scene, base)
    _postprocess(base, post, scene)

    audio = scene.get("audio")
    if audio and Path(audio).exists():
        _mux_audio(post, audio, final)
    else:
        Path(post).replace(final)
    return final


def render_chapter(scenes: list, out: str):
    """章全体: 各シーンを描いて結合。"""
    clip_dir = BUILD / "clips"
    clip_dir.mkdir(parents=True, exist_ok=True)
    clips = [render_scene(s, clip_dir) for s in scenes]

    lst = clip_dir / "concat.txt"
    lst.write_text("".join(f"file '{c}'\n" for c in clips))
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", out],
                   stderr=subprocess.DEVNULL, check=True)
    print(f"  完了: {out}")

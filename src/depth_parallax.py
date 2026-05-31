"""
depth_parallax.py — ★このパイプラインの主役★

静止画 → 深度推定 → 2.5Dパララックス（立体的なカメラ移動）→ 動くクリップ。
平面的なケンバーンズと違い、奥行きを持った没入感のある動きを生成する。

3段フォールバック:
  1. DepthFlow（GPUシェーダー・最速・最高品質）があれば使う
  2. なければ自前の PyTorch grid_sample パララックス（依存ゼロ・必ず動く）
  3. CUDA が無ければ CPU で動作（遅いが動く）

深度推定: Depth Anything V2 Small（transformers）。無ければ放射状の擬似深度。
"""
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

W, H, FPS = 1920, 1080, 24
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

_depth_model = None
_depth_processor = None


# ─────────────────────────────────────────────
# 深度推定
# ─────────────────────────────────────────────
def estimate_depth(image: Image.Image) -> np.ndarray:
    """
    画像から深度マップ（0=遠い〜1=近い、float32 H×W）を推定。
    Depth Anything V2 が使えればそれを、無ければ放射状の擬似深度を返す。
    """
    global _depth_model, _depth_processor
    try:
        if _depth_model is None:
            from transformers import AutoImageProcessor, AutoModelForDepthEstimation
            name = "depth-anything/Depth-Anything-V2-Small-hf"
            print("  [depth] Depth Anything V2 をロード中...")
            _depth_processor = AutoImageProcessor.from_pretrained(name)
            _depth_model = AutoModelForDepthEstimation.from_pretrained(name).to(DEVICE)

        inputs = _depth_processor(images=image, return_tensors="pt").to(DEVICE)
        with torch.no_grad():
            depth = _depth_model(**inputs).predicted_depth  # (1, h, w)
        depth = F.interpolate(
            depth.unsqueeze(1), size=(image.height, image.width),
            mode="bicubic", align_corners=False
        ).squeeze().cpu().numpy()
        # 正規化 0..1（大きいほど近い）
        d = (depth - depth.min()) / (depth.max() - depth.min() + 1e-8)
        return d.astype(np.float32)
    except Exception as e:
        print(f"  [depth] DepthAnything 使用不可 → 放射状擬似深度: {e}")
        return _radial_fake_depth(image.height, image.width)


def _radial_fake_depth(h: int, w: int) -> np.ndarray:
    """中央が近く周辺が遠い、放射状の擬似深度（フォールバック）。"""
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h / 2, w / 2
    dist = np.sqrt(((yy - cy) / cy) ** 2 + ((xx - cx) / cx) ** 2)
    return (1.0 - np.clip(dist / 1.414, 0, 1)).astype(np.float32)


# ─────────────────────────────────────────────
# パララックス生成
# ─────────────────────────────────────────────
def animate_parallax(image: Image.Image, output: str,
                     duration: float = 6.0,
                     motion: str = "orbit",
                     amplitude: float = 0.04,
                     depth: np.ndarray = None) -> str:
    """
    静止画をパララックス動画クリップに変換。
    motion: "orbit"（円運動）| "dolly"（前後）| "pan_lr"（左右）| "zoom_in"
    amplitude: カメラ移動量（画面比、0.02〜0.06が自然）
    """
    if _has_depthflow():
        return _animate_with_depthflow(image, output, duration, motion, amplitude)
    return _animate_with_gridsample(image, output, duration, motion, amplitude, depth)


def _has_depthflow() -> bool:
    try:
        import depthflow  # noqa
        return True
    except ImportError:
        return False


def _animate_with_depthflow(image, output, duration, motion, amplitude) -> str:
    """DepthFlow（GPUシェーダー）でパララックス生成。最速・穴埋め良。"""
    try:
        from depthflow.scene import DepthScene
        tmp = Path(tempfile.mkdtemp())
        img_path = tmp / "src.png"
        image.save(img_path)

        scene = DepthScene(backend="headless")
        scene.input(image=str(img_path))
        # 動きプリセット（DepthFlowのAnimationを設定）
        scene.config.animation.clear()
        if motion == "orbit":
            scene.add_animation(scene.preset.Orbital(intensity=amplitude * 25))
        elif motion == "dolly":
            scene.add_animation(scene.preset.Dolly(intensity=amplitude * 25))
        elif motion == "zoom_in":
            scene.add_animation(scene.preset.Zoom(intensity=amplitude * 25))
        else:  # pan_lr
            scene.add_animation(scene.preset.Horizontal(intensity=amplitude * 25))

        scene.main(output=output, fps=FPS, time=duration,
                   width=W, height=H, quality=90)
        print(f"  [parallax/DepthFlow] {output}")
        return output
    except Exception as e:
        print(f"  [parallax] DepthFlow失敗 → grid_sampleにフォールバック: {e}")
        return _animate_with_gridsample(image, output, duration, motion, amplitude, None)


def _animate_with_gridsample(image, output, duration, motion, amplitude, depth) -> str:
    """
    自前パララックス（PyTorch grid_sample）。依存ゼロ・必ず動く。
    深度に応じて手前ほど大きく画素を変位させ、カメラ移動を擬似する。
    穴は境界パディングで埋める（微小な動きなら自然に見える）。
    """
    if depth is None:
        depth = estimate_depth(image)

    # テンソル化: 画像 (1,3,H,W)、視差マップ disparity (1,1,H,W)
    img = image.convert("RGB").resize((W, H), Image.LANCZOS)
    img_t = torch.from_numpy(np.array(img)).permute(2, 0, 1).unsqueeze(0).float().to(DEVICE) / 255.0

    d = torch.from_numpy(depth).unsqueeze(0).unsqueeze(0).float().to(DEVICE)
    d = F.interpolate(d, size=(H, W), mode="bilinear", align_corners=False)
    # 近いほど大きく動く。視差を [-amp, +amp] の画面比に
    disparity = (d - 0.5) * 2.0  # -1..1

    # 基本サンプリング格子
    ys, xs = torch.meshgrid(
        torch.linspace(-1, 1, H, device=DEVICE),
        torch.linspace(-1, 1, W, device=DEVICE),
        indexing="ij",
    )
    base = torch.stack([xs, ys], dim=-1).unsqueeze(0)  # (1,H,W,2)

    n_frames = int(duration * FPS)
    proc = _open_pipe(output)
    try:
        for i in range(n_frames):
            t = i / max(n_frames - 1, 1)
            ox, oy, zoom = _camera_path(motion, t, amplitude)

            grid = base.clone()
            # 深度による視差変位（x,y）。disparityはbroadcast
            grid[..., 0] = grid[..., 0] + ox * disparity[0, 0]
            grid[..., 1] = grid[..., 1] + oy * disparity[0, 0]
            # ズーム（中心拡大）
            grid = grid / zoom

            warped = F.grid_sample(img_t, grid, mode="bilinear",
                                   padding_mode="border", align_corners=True)
            frame = (warped[0].clamp(0, 1) * 255).byte().permute(1, 2, 0).contiguous()
            proc.stdin.write(frame.cpu().numpy().tobytes())
        print(f"  [parallax/grid_sample] {output}")
    finally:
        proc.stdin.close()
        proc.wait()
    return output


def _camera_path(motion: str, t: float, amp: float):
    """t(0..1) における (x変位, y変位, ズーム倍率) を返す。"""
    ease = 0.5 - 0.5 * math.cos(math.pi * t)  # ease-in-out
    if motion == "orbit":
        ang = 2 * math.pi * t
        return amp * math.cos(ang), amp * math.sin(ang) * 0.6, 1.0 + amp * 0.5
    if motion == "dolly":
        return 0.0, 0.0, 1.0 + amp * 4 * ease
    if motion == "zoom_in":
        return 0.0, 0.0, 1.0 + amp * 6 * ease
    if motion == "pan_lr":
        return amp * (2 * ease - 1) * 2, 0.0, 1.0 + amp
    return 0.0, 0.0, 1.0 + amp * ease


def _open_pipe(output: str) -> subprocess.Popen:
    """ffmpeg 生フレーム入力パイプ。NVENC優先、無ければx264。"""
    codec = "h264_nvenc" if DEVICE.type == "cuda" else "libx264"
    cmd = [
        "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{W}x{H}", "-pix_fmt", "rgb24", "-r", str(FPS), "-i", "-",
        "-c:v", codec, "-preset", "p4" if codec == "h264_nvenc" else "fast",
        "-pix_fmt", "yuv420p", output,
    ]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)


def free_depth_model():
    """VRAM解放（次のモデルをロードする前に呼ぶ）。"""
    global _depth_model, _depth_processor
    _depth_model = None
    _depth_processor = None
    if DEVICE.type == "cuda":
        torch.cuda.empty_cache()

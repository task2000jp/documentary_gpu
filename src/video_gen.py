"""
video_gen.py — LTX-Video によるテキスト動画生成（hero shotのみ）
T4(15GB)で唯一余裕のある動画生成モデル。全編には使わず、
「蒸気機関が動く瞬間」など3〜5秒のキー場面に限定して使う。
"""
import torch
from pathlib import Path

W, H, FPS = 1920, 1080, 24
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
_pipe = None


def _load():
    """LTX-Video パイプラインをロード。"""
    from diffusers import LTXPipeline
    pipe = LTXPipeline.from_pretrained(
        "Lightricks/LTX-Video", torch_dtype=torch.bfloat16)
    pipe.enable_model_cpu_offload()
    return pipe


def generate(prompt: str, out: str, duration: float = 4.0,
             width: int = 1280, height: int = 720) -> str:
    """
    プロンプトから短尺動画を生成し out(mp4) に保存。
    LTXが使えない環境ではエラーを投げる（呼び出し側でparallaxにフォールバック想定）。
    """
    global _pipe
    if _pipe is None:
        print("  [video_gen] LTX-Video をロード中...")
        _pipe = _load()

    n_frames = int(duration * FPS)
    print(f"  [video_gen] {prompt[:50]}... ({duration}s)")
    frames = _pipe(prompt=prompt, width=width, height=height,
                   num_frames=n_frames, num_inference_steps=30).frames[0]

    from diffusers.utils import export_to_video
    export_to_video(frames, out, fps=FPS)
    return out


def free():
    global _pipe
    _pipe = None
    if DEVICE == "cuda":
        torch.cuda.empty_cache()

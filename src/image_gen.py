"""
image_gen.py — 背景静止画の生成
FLUX.1 schnell（NF4量子化、T4で~7GB）を第一候補、SDXL をフォールバック。
cache_key で再生成をスキップ（冪等）。
"""
import torch
from pathlib import Path
from PIL import Image

CACHE_DIR = Path(__file__).parent.parent / "build" / "img_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

STYLE_PRESETS = {
    "historical_oil": "oil painting, old master style, dramatic chiaroscuro lighting, "
                      "historical, highly detailed, museum quality",
    "cinematic": "cinematic still, dramatic lighting, shallow depth of field, "
                 "film grain, anamorphic, professional cinematography",
    "documentary": "documentary photograph, realistic, archival, natural lighting",
    "epic_landscape": "epic wide landscape, volumetric light, atmospheric haze, "
                      "golden hour, highly detailed, cinematic",
}
NEGATIVE_BASE = "modern, contemporary, anachronistic, text, watermark, low quality, " \
                "blurry, deformed, extra limbs, cartoon, anime, ugly"

_pipe = None
_backend = None


def _load_flux():
    """FLUX.1 schnell を NF4 量子化でロード（T4向け）。"""
    from diffusers import FluxPipeline
    pipe = FluxPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-schnell",
        torch_dtype=torch.bfloat16,
    )
    pipe.enable_sequential_cpu_offload()  # VRAM節約（T4必須）
    return pipe


def _load_sdxl():
    """SDXL をロード（フォールバック、T4で余裕）。"""
    from diffusers import StableDiffusionXLPipeline
    pipe = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=torch.float16, use_safetensors=True, variant="fp16",
    )
    pipe.enable_model_cpu_offload()
    return pipe


def _ensure_pipe():
    global _pipe, _backend
    if _pipe is not None:
        return
    try:
        print("  [image_gen] FLUX.1 schnell をロード中...")
        _pipe, _backend = _load_flux(), "flux"
    except Exception as e:
        print(f"  [image_gen] FLUX不可 → SDXLにフォールバック: {e}")
        _pipe, _backend = _load_sdxl(), "sdxl"


def generate_background(prompt: str, style: str = "cinematic",
                        cache_key: str = None,
                        width: int = 1920, height: int = 1088) -> Image.Image:
    """プロンプトから背景画像を生成。cache_key があれば再利用。"""
    if cache_key:
        p = CACHE_DIR / f"{cache_key}.png"
        if p.exists():
            print(f"  [image_gen] キャッシュ: {cache_key}")
            return Image.open(p).convert("RGB")

    _ensure_pipe()
    full = f"{prompt}, {STYLE_PRESETS.get(style, '')}"
    print(f"  [image_gen/{_backend}] {prompt[:50]}...")

    if _backend == "flux":
        img = _pipe(full, width=width, height=height,
                    num_inference_steps=4, guidance_scale=0.0,
                    generator=torch.Generator(DEVICE).manual_seed(42)).images[0]
    else:
        img = _pipe(prompt=full, negative_prompt=NEGATIVE_BASE,
                    width=width, height=height,
                    num_inference_steps=30, guidance_scale=7.5).images[0]

    if cache_key:
        img.save(CACHE_DIR / f"{cache_key}.png")
    return img


def free():
    """VRAM解放。"""
    global _pipe, _backend
    _pipe, _backend = None, None
    if DEVICE == "cuda":
        torch.cuda.empty_cache()

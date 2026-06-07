"""
manim_render.py — Manim ヒーロー図カットを 1クリップとして焼くブリッジ

renderer._base_clip の background.type=="manim" から呼ばれる。
Manim は自前で mp4 を吐くので、それを本編の解像度/FPS に合わせて生成し、
所定の out パスへコピーするだけ。後段の _postprocess が grade/text 等を被せる。

依存(Manim本体・cairo/pango)は manim カット使用時のみ。lazy import。
Colab: !apt-get install -y libcairo2-dev libpango1.0-dev / !pip install manim
"""
import glob
import shutil
import subprocess
import tempfile
from pathlib import Path

SCENES_FILE = Path(__file__).parent / "manim_scenes.py"
W, H, FPS = 1920, 1080, 24


def render(scene_name: str, out: str, fps: int = FPS, w: int = W, h: int = H) -> str:
    """manim_scenes.py 内の Scene クラスを描画 → out(mp4)。"""
    media = tempfile.mkdtemp()
    cmd = [
        "manim", "render", "-qh",
        "--fps", str(fps), "-r", f"{w},{h}",
        "--media_dir", media, "--format", "mp4",
        str(SCENES_FILE), scene_name,
    ]
    print(f"  [manim] render {scene_name} ({w}x{h}@{fps})")
    subprocess.run(cmd, check=True)
    found = glob.glob(f"{media}/videos/**/{scene_name}.mp4", recursive=True)
    if not found:
        raise RuntimeError(f"manim 出力が見つかりません: {scene_name}")
    shutil.copy(found[0], out)
    return out

"""
manim_render.py — Manim ヒーロー図カットを 1クリップとして焼くブリッジ

renderer._base_clip の background.type=="manim" から呼ばれる。
Manim は自前で mp4 を吐くので、それを生成して所定の out へコピーするだけ。
後段の _postprocess が grade/text 等を被せる。

速度: 本編は1920x1080だが Manim は 720p で描画する。renderer の decode pipe が
1080p へ自動拡大するため、Cairo の CPU 描画コストを ~2x 削減できる（見た目ほぼ同等）。
保護: timeout を超えたら TimeoutExpired を送出 → 呼び出し側がプレースホルダで継続。

依存(Manim本体・cairo/pango)は manim カット使用時のみ。lazy import。
Colab: !apt-get install -y libcairo2-dev libpango1.0-dev / !pip install manim
"""
import glob
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

SCENES_FILE = Path(__file__).parent / "manim_scenes.py"
RENDER_W, RENDER_H, FPS = 1280, 720, 24   # 720pで描画 → decode pipe が1080pへ拡大
TIMEOUT = 600                              # 秒。超過=ハングとみなし TimeoutExpired


def render(scene_name: str, out: str, fps: int = FPS,
           w: int = RENDER_W, h: int = RENDER_H, timeout: int = TIMEOUT) -> str:
    """manim_scenes.py 内の Scene クラスを描画 → out(mp4)。"""
    media = tempfile.mkdtemp()
    cmd = [
        "manim", "render", "-qm",
        "--fps", str(fps), "-r", f"{w},{h}",
        "--media_dir", media, "--format", "mp4",
        str(SCENES_FILE), scene_name,
    ]
    print(f"  [manim] render {scene_name} ({w}x{h}@{fps}, 目安1-2分)...")
    t0 = time.time()
    subprocess.run(cmd, check=True, timeout=timeout)
    found = glob.glob(f"{media}/videos/**/{scene_name}.mp4", recursive=True)
    if not found:
        raise RuntimeError(f"manim 出力が見つかりません: {scene_name}")
    shutil.copy(found[0], out)
    print(f"  [manim] 完了 {time.time() - t0:.0f}s → {out}")
    return out

"""
character.py — SadTalker / LivePortrait による肖像画アニメーション
静止画の人物に音声を与えて口パク・表情を生成する。
"""
import subprocess
import tempfile
from pathlib import Path


def animate_portrait_sadtalker(
    portrait_path: str,
    audio_path: str,
    output_path: str,
    sadtalker_dir: str = "/content/SadTalker",
) -> str:
    """
    SadTalker で肖像画を音声に合わせてアニメーション。
    Colab での使用を想定（sadtalker_dir はクローン先）。

    Returns: output_path（生成された MP4 パス）
    """
    cmd = [
        "python", f"{sadtalker_dir}/inference.py",
        "--driven_audio", audio_path,
        "--source_image", portrait_path,
        "--result_dir", str(Path(output_path).parent),
        "--still",           # カメラ固定（ドキュメンタリー向け）
        "--preprocess", "full",
        "--enhancer", "gfpgan",  # 高解像度化
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [character] SadTalker エラー: {result.stderr[-500:]}")
        return None

    print(f"  [character] アニメーション生成完了: {output_path}")
    return output_path


def animate_portrait_liveportrait(
    portrait_path: str,
    audio_path: str,
    output_path: str,
    liveportrait_dir: str = "/content/LivePortrait",
) -> str:
    """
    LivePortrait による肖像画アニメーション（SadTalker のフォールバック）。
    """
    cmd = [
        "python", f"{liveportrait_dir}/inference.py",
        "--source", portrait_path,
        "--driving_audio", audio_path,
        "--output", output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [character] LivePortrait エラー: {result.stderr[-500:]}")
        return None

    return output_path


def animate_portrait(portrait_path: str, audio_path: str,
                     output_path: str, driver: str = "sadtalker") -> str:
    """統合エントリポイント。driver: 'sadtalker' | 'liveportrait'"""
    if driver == "sadtalker":
        return animate_portrait_sadtalker(portrait_path, audio_path, output_path)
    elif driver == "liveportrait":
        return animate_portrait_liveportrait(portrait_path, audio_path, output_path)
    else:
        raise ValueError(f"未対応の driver: {driver}")

"""
narration.py — ナレーション音声生成
Style-Bert-VITS2（日本語無料最高峰）を第一候補、edge-tts をフォールバック。
cache_key（= seg_id）で再生成スキップ。
"""
import asyncio
from pathlib import Path

AUDIO_DIR = Path(__file__).parent.parent / "build" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

_sbv2 = None
_DEFAULT_EDGE_VOICE = "ja-JP-KeitaNeural"


def _load_sbv2():
    """Style-Bert-VITS2 モデルをロード。"""
    from style_bert_vits2.tts_model import TTSModel
    from style_bert_vits2.nlp import bert_models
    from style_bert_vits2.constants import Languages
    import torch

    # 日本語BERTを準備
    bert_models.load_model(Languages.JP, "ku-nlp/deberta-v2-large-japanese-char-wwm")
    bert_models.load_tokenizer(Languages.JP, "ku-nlp/deberta-v2-large-japanese-char-wwm")

    model_dir = Path(__file__).parent.parent / "models" / "sbv2"
    # litagin の jvnv モデル等を models/sbv2/ に配置している前提
    safetensors = next(model_dir.glob("*.safetensors"))
    config = model_dir / "config.json"
    style = model_dir / "style_vectors.npy"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return TTSModel(model_path=safetensors, config_path=config,
                    style_vec_path=style, device=device)


def synthesize(text: str, seg_id: str,
               style: str = "Neutral", style_weight: float = 1.0,
               force: bool = False) -> str:
    """
    テキストを音声WAVに変換。build/audio/{seg_id}.wav に保存しパスを返す。
    SBV2 が使えればそれを、ダメなら edge-tts に自動フォールバック。
    """
    out = AUDIO_DIR / f"{seg_id}.wav"
    if out.exists() and out.stat().st_size > 5000 and not force:
        return str(out)

    global _sbv2
    try:
        if _sbv2 is None:
            print("  [narration] Style-Bert-VITS2 をロード中...")
            _sbv2 = _load_sbv2()
        import soundfile as sf
        sr, audio = _sbv2.infer(text=text, style=style, style_weight=style_weight)
        sf.write(str(out), audio, sr)
        print(f"  [narration/SBV2] {seg_id}: {text[:24]}...")
        return str(out)
    except Exception as e:
        print(f"  [narration] SBV2不可 → edge-tts: {e}")
        return _synthesize_edge(text, out)


def _synthesize_edge(text: str, out: Path) -> str:
    """edge-tts フォールバック（前プロジェクトと同等）。"""
    import edge_tts

    async def _run():
        mp3 = out.with_suffix(".mp3")
        await edge_tts.Communicate(text, _DEFAULT_EDGE_VOICE).save(str(mp3))
        # mp3 → wav 変換（48kHz stereo）
        import subprocess
        subprocess.run(["ffmpeg", "-y", "-i", str(mp3), "-ar", "48000",
                        "-ac", "2", str(out)],
                       stderr=subprocess.DEVNULL, check=True)
        mp3.unlink(missing_ok=True)

    asyncio.run(_run())
    print(f"  [narration/edge] {out.stem}")
    return str(out)


def measure(seg_id: str) -> float:
    """WAVの長さ（秒）を返す。シーン尺の決定に使う。"""
    import wave
    p = AUDIO_DIR / f"{seg_id}.wav"
    with wave.open(str(p), "rb") as w:
        return w.getnframes() / w.getframerate()


def free():
    global _sbv2
    _sbv2 = None
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass

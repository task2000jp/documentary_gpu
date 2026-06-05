"""
render_music.py — MIDI → 音声 → ミックス → マスタリング（Colab・MP2/MP3）

  python scripts/render_music.py build/music/ch6.mid --out build/music/ch6.wav

工程（実レコーディングの再現）:
  ① FluidSynth + SoundFont で MIDI → wav（楽器音化）
  ② pedalboard で空間/EQ/コンプ（ミックス）
  ③ pyloudnorm で -16 LUFS 正規化（マスタリング・content_design要件）

依存は Colab 側（fluidsynth / pedalboard / pyloudnorm / soundfile）。
ローカル(設計用)には入れない。SoundFontは fluid-soundfont-gm を想定。
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Colab標準のSoundFont候補（apt install fluid-soundfont-gm）
SOUNDFONT_CANDIDATES = [
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/default-GM.sf2",
    "/usr/share/soundfonts/FluidR3_GM.sf2",
]
TARGET_LUFS = -16.0
SR = 44100


def _find_soundfont(explicit: str | None) -> str:
    if explicit and Path(explicit).exists():
        return explicit
    for c in SOUNDFONT_CANDIDATES:
        if Path(c).exists():
            return c
    print("ERROR: SoundFontが見つかりません。Colabで:")
    print("  !apt-get install -y fluidsynth fluid-soundfont-gm")
    sys.exit(1)


def midi_to_wav(midi: str, soundfont: str, out_wav: str):
    """① FluidSynth CLI で MIDI → wav。"""
    if not shutil.which("fluidsynth"):
        print("ERROR: fluidsynth未インストール → !apt-get install -y fluidsynth")
        sys.exit(1)
    Path(out_wav).parent.mkdir(parents=True, exist_ok=True)
    cmd = ["fluidsynth", "-ni", "-g", "0.8", "-r", str(SR),
           "-F", out_wav, soundfont, midi]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  ① 楽器音化: {out_wav}")


def mix_and_master(in_wav: str, out_wav: str, style: str = "orchestral"):
    """② ミックス（空間/EQ/コンプ）→ ③ -16 LUFS マスタリング。"""
    import numpy as np
    import soundfile as sf
    try:
        from pedalboard import (Pedalboard, Reverb, Compressor,
                                HighpassFilter, Limiter, Delay, Chorus)
        have_pb = True
    except ImportError:
        have_pb = False
        print("  [warn] pedalboard未導入 → ミックス省略（マスタリングのみ）")

    audio, sr = sf.read(in_wav, dtype="float32")
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=-1)  # mono→stereo

    if have_pb:
        if style == "fingerstyle":
            # Knopfler風: スラップ気味ディレイ + 軽いコーラス + 広い残響
            chain = [
                HighpassFilter(cutoff_frequency_hz=60),
                Compressor(threshold_db=-16, ratio=2.0),
                Chorus(rate_hz=0.6, depth=0.18, mix=0.2),
                Delay(delay_seconds=0.28, feedback=0.28, mix=0.22),  # signature delay
                Reverb(room_size=0.62, damping=0.35, wet_level=0.16, dry_level=0.88),
                Limiter(threshold_db=-1.0),
            ]
            print("  ② ミックス(fingerstyle): HPF→Comp→Chorus→Delay→Reverb→Limiter")
        else:
            chain = [
                HighpassFilter(cutoff_frequency_hz=35),
                Compressor(threshold_db=-18, ratio=2.5),
                Reverb(room_size=0.55, damping=0.4, wet_level=0.18, dry_level=0.85),
                Limiter(threshold_db=-1.0),
            ]
            print("  ② ミックス(orchestral): HPF→Comp→Reverb→Limiter")
        board = Pedalboard(chain)
        audio = board(audio, sr)

    # ③ -16 LUFS 正規化
    try:
        import pyloudnorm as pyln
        meter = pyln.Meter(sr)
        loudness = meter.integrated_loudness(audio)
        audio = pyln.normalize.loudness(audio, loudness, TARGET_LUFS)
        print(f"  ③ マスタリング: {loudness:.1f} → {TARGET_LUFS} LUFS")
    except ImportError:
        print("  [warn] pyloudnorm未導入 → LUFS正規化スキップ")

    import numpy as np
    audio = np.clip(audio, -1.0, 1.0)
    sf.write(out_wav, audio, sr)
    print(f"  完了: {out_wav}")


def main():
    ap = argparse.ArgumentParser(description="MIDI→音声→ミックス→マスタリング")
    ap.add_argument("midi", help="入力MIDI（build/music/ch6.mid）")
    ap.add_argument("--out", default=None, help="出力wav（省略時 同名.wav）")
    ap.add_argument("--soundfont", default=None, help="SoundFont(.sf2)パス")
    ap.add_argument("--style", default="orchestral",
                    choices=["orchestral", "fingerstyle"],
                    help="ミックススタイル（fingerstyle=Knopfler風ディレイ）")
    args = ap.parse_args()

    if not Path(args.midi).exists():
        print(f"エラー: {args.midi} がありません。先に compose_music.py を実行。")
        sys.exit(1)

    sf2 = _find_soundfont(args.soundfont)
    out = args.out or str(Path(args.midi).with_suffix(".wav"))
    raw = str(Path(out).with_suffix(".raw.wav"))

    print(f"SoundFont: {sf2}")
    midi_to_wav(args.midi, sf2, raw)
    mix_and_master(raw, out, style=args.style)
    Path(raw).unlink(missing_ok=True)
    print(f"\n劇伴完成: {out}")


if __name__ == "__main__":
    main()

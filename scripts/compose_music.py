"""
compose_music.py — キュー仕様 → MIDI（理論based作曲・MP1）

  python scripts/compose_music.py cues/ch6.json
  python scripts/compose_music.py cues/ch6.json --out build/music/ch6.mid

MIDIまではローカル（music21・純Python）。
MIDI→音声（FluidSynth/SoundFont）・ミックス・マスタリングは Colab。
"""
import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "src"))

from music import composer  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="理論based作曲: cue → MIDI")
    ap.add_argument("cue", help="キュー仕様JSON（cues/ch6.json）")
    ap.add_argument("--out", default=None, help="出力MIDI（省略時 build/music/<id>.mid）")
    args = ap.parse_args()

    if not Path(args.cue).exists():
        print(f"エラー: {args.cue} がありません")
        sys.exit(1)

    cue = json.loads(Path(args.cue).read_text())
    out = args.out or str(BASE / "build" / "music" / f"{cue.get('id', Path(args.cue).stem)}.mid")
    path = composer.write_midi(cue, out)

    print(f"作曲完了: {path}")
    print(f"  調/旋法 : {cue.get('key','C')} {cue.get('mode','ionian')}")
    print(f"  テンポ  : {cue.get('tempo',72)} BPM")
    print(f"  主題    : {cue.get('motif','victory')} ({cue.get('motif_treatment','full')})")
    print(f"  楽器    : {', '.join(cue.get('instrumentation', []))}")
    print(f"  尺      : {cue.get('duration',60)}秒")
    print("  → Colabで FluidSynth レンダリング（MP2）")


if __name__ == "__main__":
    main()

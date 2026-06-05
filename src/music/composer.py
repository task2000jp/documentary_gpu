"""
composer.py — キュー仕様(JSON) → MIDIスコア（music21・理論based）

旋法/調/テンポ・和声進行（旋法ディアトニック三和音）・ライトモチーフを
treatment適用して配置し、楽器ごとにトラック分離したMIDIを書き出す。
（=マルチトラック録音の素。Colab側でFluidSynth→ステム音声→ミックス）

設計根拠: docs/music_system.md / music_schema.md
"""
from __future__ import annotations

import json
from pathlib import Path

from music21 import stream, note, chord, tempo, metadata, instrument, pitch

from . import leitmotif

# General MIDI プログラム番号
GM = {
    "strings": 48, "organ": 19, "low_brass": 57, "brass": 61,
    "choir": 52, "piano": 0, "harp": 46, "flute": 73, "timpani": 47,
    "solo_cello": 42, "solo_violin": 40, "oboe": 68, "horn": 60,
}

# 旋法ごとのデフォルト和声進行（旋法非指定時）
DEFAULT_PROGRESSION = {
    "ionian":     ["I", "IV", "V", "I"],
    "major":      ["I", "IV", "V", "I"],
    "aeolian":    ["i", "VI", "VII", "i"],
    "minor":      ["i", "VI", "VII", "i"],
    "dorian":     ["i", "IV", "i", "VII"],
    "phrygian":   ["i", "II", "i", "i"],
    "lydian":     ["I", "II", "I", "I"],
    "mixolydian": ["I", "VII", "IV", "I"],
}

# dynamic_arc → 各和声スロットの velocity 係数（0..1）を返す
def _arc_curve(arc: str, n: int) -> list[float]:
    if n <= 1:
        return [0.8]
    xs = [i / (n - 1) for i in range(n)]
    if arc == "build":
        return [0.45 + 0.5 * x for x in xs]
    if arc == "decay":
        return [0.9 - 0.5 * x for x in xs]
    if arc == "swell":
        return [0.45 + 0.5 * (1 - abs(2 * x - 1)) for x in xs]
    return [0.78 for _ in xs]  # sustain


_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7}


def _roman_to_degree(rn: str) -> int:
    return _ROMAN.get(rn.strip().lower(), 1)


def _diatonic_triad(tonic_midi: int, mode: str, degree: int) -> list[int]:
    """旋法ディアトニックな三和音（スケール内の三度堆積）。modal-correct。"""
    scale = leitmotif.MODES.get(mode, leitmotif.MODES["ionian"])
    def deg_semi(d: int) -> int:
        idx = (d - 1) % 7
        octv = (d - 1) // 7
        return scale[idx] + 12 * octv
    root = deg_semi(degree)
    third = deg_semi(degree + 2)
    fifth = deg_semi(degree + 4)
    return [tonic_midi + root, tonic_midi + third, tonic_midi + fifth]


def _part(program: int, name: str) -> stream.Part:
    p = stream.Part()
    instr = instrument.Instrument()
    instr.midiProgram = program
    instr.partName = name
    p.insert(0, instr)
    return p


def compose_cue(cue: dict) -> stream.Score:
    key_name = cue.get("key", "C")
    mode = cue.get("mode", "ionian")
    bpm = float(cue.get("tempo", 72))
    duration_sec = float(cue.get("duration", 60))
    insts = cue.get("instrumentation", ["strings"])
    arc = cue.get("dynamic_arc", "sustain")

    tonic_midi = pitch.Pitch(f"{key_name}3").midi  # 低めの基準
    total_q = duration_sec * bpm / 60.0            # 全体の四分音符数

    # 和声進行
    prog = cue.get("harmony")
    romans = (prog.split("-") if isinstance(prog, str) and prog
              else DEFAULT_PROGRESSION.get(mode, ["I", "IV", "V", "I"]))
    n_slots = max(len(romans), 1)
    # 進行を繰り返して尺を満たす（最低でも1巡）
    reps = max(1, round(total_q / (n_slots * 4)))   # 1和音=全音符(4拍)想定
    slots = (romans * reps)
    slot_q = total_q / len(slots)
    vels = _arc_curve(arc, len(slots))

    score = stream.Score()
    score.insert(0, metadata.Metadata())
    score.metadata.title = cue.get("id", "cue")
    score.insert(0, tempo.MetronomeMark(number=bpm))

    # ── 役割割り当て ──
    melodic = insts[0]
    pad_insts = insts[1:2] or [insts[0]]
    bass_inst = insts[-1]

    # ── 和声パッド ──
    pad = _part(GM.get(pad_insts[0], 48), f"pad:{pad_insts[0]}")
    bass = _part(GM.get(bass_inst, 57), f"bass:{bass_inst}")
    for i, rn in enumerate(slots):
        deg = _roman_to_degree(rn)
        triad = _diatonic_triad(tonic_midi + 12, mode, deg)  # パッドは1oct上
        v = int(40 + 60 * vels[i])
        ch = chord.Chord(triad, quarterLength=slot_q)
        ch.volume.velocity = v
        pad.append(ch)
        # バス＝根音（さらに1oct下）
        b = note.Note(triad[0] - 24, quarterLength=slot_q)
        b.volume.velocity = int(v * 0.9)
        bass.append(b)

    # ── 主題（ライトモチーフ）──
    mel = _part(GM.get(melodic, 48), f"melody:{melodic}")
    realized = leitmotif.realize(
        cue.get("motif", "victory"),
        tonic_midi + 24,                       # 主題は2oct上で歌わせる
        mode,
        cue.get("motif_treatment", "full"),
    )
    # 冒頭に短い無音、その後 主題提示 → 中盤で再提示（理論的な再現）
    mel.append(note.Rest(quarterLength=min(4.0, total_q * 0.1)))
    peak_vel = max(vels)
    for reprise in (False, True):
        if reprise:
            gap = total_q * 0.4
            mel.append(note.Rest(quarterLength=max(2.0, gap)))
        for p, ql, vsc in realized:
            if p is None:
                mel.append(note.Rest(quarterLength=ql))
                continue
            n = note.Note(p, quarterLength=ql)
            base = peak_vel if reprise else 0.7
            n.volume.velocity = int(max(30, min(127, 127 * base * vsc)))
            mel.append(n)

    score.insert(0, mel)
    score.insert(0, pad)
    score.insert(0, bass)
    return score


def write_midi(cue: dict, out_path: str) -> str:
    score = compose_cue(cue)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    score.write("midi", fp=out_path)
    return out_path

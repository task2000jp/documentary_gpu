"""
leitmotif.py — ライトモチーフ体系（理論の心臓）

神学的意味を持つ動機を「スケール度数」で定義する。絶対音高でなく度数で持つので、
旋法・調を変えるだけで同じ動機が別の感情に変容する（=劇伴の正統手法）。

度数トークン:
  "1".."7"  : 旋法内のディアトニック度数
  "8","9".. : オクターブ上（8=1+oct, 9=2+oct, 10=3+oct ...）
  "b3","#4" : 半音変化（旋法の度数からさらに ±1）
  "r"       : 休符

設計根拠: docs/music_system.md
"""
from __future__ import annotations

# 旋法ごとの、主音からの半音オフセット（度数1..7）
MODES = {
    "ionian":     [0, 2, 4, 5, 7, 9, 11],
    "dorian":     [0, 2, 3, 5, 7, 9, 10],
    "phrygian":   [0, 1, 3, 5, 7, 8, 10],
    "lydian":     [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "aeolian":    [0, 2, 3, 5, 7, 8, 10],
    # 別名
    "major":      [0, 2, 4, 5, 7, 9, 11],
    "minor":      [0, 2, 3, 5, 7, 8, 10],
}

# モチーフ = [(度数トークン, 音価(四分音符=1.0)), ...]
# 神学的意味は docs/music_system.md の表を参照。
MOTIFS = {
    # 勝利（Christus Victor）: 完全音程の上昇＝英雄的・開放
    "victory":  [("1", 1.0), ("5", 1.0), ("8", 1.5), ("10", 0.5), ("8", 2.0)],
    # 束縛（恐れ・罪悪感）: 狭い・執拗・短二度で circling
    "bondage":  [("1", 0.5), ("b2", 0.5), ("1", 0.5), ("7", 0.5),
                 ("1", 0.5), ("b2", 0.5), ("1", 1.0)],
    # 創造・シャローム: 長三和音の開放・穏やか
    "shalom":   [("1", 1.5), ("3", 1.0), ("5", 1.5), ("8", 2.0)],
    # 問い・神秘: 解決しない浮遊（リディア的）
    "question": [("5", 1.0), ("6", 1.0), ("7", 1.0), ("#4", 1.5), ("5", 1.5)],
    # ハイランド（Knopfler風・スコットランド英雄譚）: ミクソリディアンの上行・歌う
    # ※オリジナル旋律（特定曲の引用ではない）。b7(ミクソリディアン)が土の匂いを出す
    "highland": [("5", 1.0), ("6", 0.5), ("8", 1.5), ("7", 0.5), ("8", 1.0),
                 ("10", 2.0), ("9", 0.5), ("8", 0.5), ("5", 2.0)],

    # ── Knopfler / Dire Straits 風アンセム（"Local Hero / Brothers in Arms" の気配）──
    # 全てオリジナル旋律・特定曲の引用なし。ミクソリディアンで歌う、間を活かす、
    # 6度跳躍・b7(7)の隣接音・オクターブ超えの最高音(10,12)が署名。提示→応答→クライマックス→帰結。
    # knopfler_call: 提示（中音域の"呼びかけ"）5→6→8へ上行、b7で陰り、本音(8)へ。
    "knopfler_call":    [("5", 1.0), ("6", 0.5), ("8", 2.0), ("7", 0.5),
                         ("8", 1.0), ("6", 0.5), ("5", 2.5)],
    # knopfler_answer: 応答（さらに上へ手を伸ばす）10で広がり、b7経由で戻る。
    "knopfler_answer":  [("8", 0.75), ("9", 0.25), ("10", 2.0), ("9", 0.5),
                         ("10", 0.5), ("8", 1.0), ("7", 0.5), ("8", 2.0)],
    # knopfler_climax: クライマックス（"鳴かせる"最高音12を長く保持）アンセムの頂点。
    "knopfler_climax":  [("8", 0.25), ("10", 0.25), ("12", 3.5), ("10", 1.0),
                         ("12", 0.5), ("10", 0.5), ("8", 2.0)],
    # knopfler_resolve: 帰結（"家路"の下行）8から主音1へ静かに着地。
    "knopfler_resolve": [("8", 1.0), ("7", 1.0), ("6", 1.0), ("5", 1.5),
                         ("3", 1.0), ("1", 3.0)],
}


def _parse_degree(token: str) -> int | None:
    """度数トークン → 半音オフセット（主音=0基準・旋法非依存の生パース用ではない）。
    実際の旋法適用は realize() で行う。ここでは (基本度数, 半音補正, オクターブ) を返す。
    戻り値: None（休符）または (degree1to7, chromatic, octave)
    """
    if token == "r":
        return None
    chrom = 0
    t = token
    while t and t[0] in "b#":
        chrom += -1 if t[0] == "b" else 1
        t = t[1:]
    n = int(t)
    octave, deg = divmod(n - 1, 7)  # n=1→deg0 oct0, n=8→deg0 oct1
    return (deg, chrom, octave)


def realize(motif_name: str, tonic_midi: int, mode: str,
            treatment: str = "full") -> list[tuple[int | None, float, float]]:
    """
    モチーフを具体的な音列に展開する。
    戻り値: [(midi_pitch or None, quarter_length, velocity_scale), ...]
      velocity_scale は 0..1（trebleの強弱・dynamic_arcとは別の動機内表現）。
    """
    scale = MODES.get(mode, MODES["ionian"])
    cells = MOTIFS.get(motif_name, MOTIFS["victory"])

    # treatment による前処理
    oct_shift = 0
    dur_scale = 1.0
    vel = 0.9
    picardy = False
    if treatment == "fragmented":
        cells = cells[:3]
        vel = 0.55
    elif treatment == "searching":
        dur_scale = 1.5
        oct_shift = -1
        vel = 0.5
    elif treatment == "triumphant":
        oct_shift = 0
        vel = 1.0
        picardy = mode in ("aeolian", "minor", "dorian", "phrygian")

    notes: list[tuple[int | None, float, float]] = []
    for i, (token, dur) in enumerate(cells):
        parsed = _parse_degree(token)
        if parsed is None:
            notes.append((None, dur * dur_scale, 0.0))
            continue
        deg, chrom, octv = parsed
        semis = scale[deg] + chrom + 12 * (octv + oct_shift)
        # ピカルディ: 終止音が短三度なら長三度へ（短調由来の勝利）
        if picardy and i == len(cells) - 1 and deg == 2:  # deg index2 = 3rd
            semis += 1
        pitch = tonic_midi + semis
        notes.append((pitch, dur * dur_scale, vel))
    return notes


def available_motifs() -> list[str]:
    return list(MOTIFS.keys())

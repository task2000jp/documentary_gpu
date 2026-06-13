# 音楽キュー定義スキーマ

キューは1章分の音楽片。`cues/<章>.json`（`scenes/<章>.json` と並行）。
理論based作曲エンジン（`src/music/composer.py`）が読み、MIDIを生成する。

## 基本構造

```jsonc
{
  "id": "ch6_reformation",     // 一意ID
  "duration": 90.0,            // 秒（章の長さに合わせる）
  "key": "D",                  // 主音（C, D, E♭ などmusic21表記）
  "mode": "dorian",            // 旋法（下表）
  "tempo": 72,                 // BPM
  "emotion": "breakthrough",   // 感情ラベル（人間用メモ）
  "motif": "victory",          // ライトモチーフ（下表）
  "motif_treatment": "triumphant", // 変容（下表）
  "instrumentation": ["strings", "organ", "low_brass"], // 先頭=主題, 中=パッド, 末=バス
  "dynamic_arc": "build",      // swell|build|sustain|decay
  "harmony": "i-VII-III-VII-i",// ローマ数字進行（任意・省略時は旋法デフォルト）
  "melody": [                  // 任意・歌構造（楽節を順に展開）。省略時はmotifを2回提示
    { "motif": "knopfler_call",   "treatment": "full", "intensity": 0.62, "breath": 2.5 },
    { "motif": "knopfler_climax", "treatment": "triumphant", "intensity": 1.0, "octave": 0 }
  ],
  "texture_layer": {           // AI質感（任意・Colab MP5）
    "prompt": "sacred reverberant choir pad, distant",
    "gain": 0.18               // 0..1 重ねる音量
  }
}
```

### melody（任意・歌構造）
楽節(phrase)を配列で並べ、提示→応答→クライマックス→帰結のような**歌の構造**を組む。
省略すると従来動作（`motif` を提示＋中盤で再提示）。各 phrase のキー:
| キー | 意味 | 既定 |
|---|---|---|
| `motif` | ライトモチーフ名 | `victory` |
| `treatment` | 変容（下表） | `full` |
| `octave` | 主題のオクターブ移動（±整数） | `0` |
| `intensity` | 音量0..1（明示しなければ後半ほど強くbuild） | 自動 |
| `breath` | 直前の楽節との間（休符・四分音符数） | `2.0` |

## mode（旋法）
| 値 | 感情 | 用途例 |
|---|---|---|
| `ionian`/`major` | 喜び・確信 | 祝福・解放・勝利 |
| `aeolian`/`minor` | 哀しみ・喪失 | 滅・警告 |
| `dorian` | 古雅・希望含みの短調 | 異教の神秘・改革前夜 |
| `phrygian` | 恐れ・緊張 | 砕く・束縛 |
| `lydian` | 驚異・超越 | 問い・神の視点 |
| `mixolydian` | 力強い古代 | 文明の栄華 |

## motif（ライトモチーフ）
| 値 | 神学的意味 |
|---|---|
| `victory` | Christus Victor・勝利（全編の背骨） |
| `bondage` | 恐れ・罪悪感の反復 |
| `shalom` | 創造・祝福・平和 |
| `question` | 問い・神秘 |
| `highland` | スコットランド英雄譚（Knopfler風・ミクソリディアン） |
| `knopfler_call` / `knopfler_answer` / `knopfler_climax` / `knopfler_resolve` | Dire Straits/Knopfler風アンセムの楽節（呼びかけ→応答→クライマックス→家路）。`melody`で連結して使う |

## motif_treatment（変容）
| 値 | 効果 |
|---|---|
| `full` | 完全提示 |
| `fragmented` | 冒頭2〜3音・疎ら（闇で断片化） |
| `searching` | 短調・遅く・低く・弱く（解放前の探求） |
| `triumphant` | 全奏・強く・短調由来はピカルディ終止（勝利） |

## instrumentation（GM楽器）
`strings organ low_brass brass choir piano harp flute timpani solo_cello solo_violin oboe horn`
- 先頭 = 主題（メロディ）, 2番目 = 和声パッド, 末尾 = バス

## 完全な例（cues/ch6.json）
プロローグ=`question`/lydian、第2章砕く=`bondage`/phrygian、
第6章改革=`victory`/dorian→`triumphant`、エピローグ=`victory`/ionian など
content_design.md の感情アークに対応させる。

## 設計メモ
- `id` を `scenes/<章>.json` と対応させると、章の映像と音楽が紐づく。
- 同じ `motif` でも `mode`/`treatment` を変えれば別の感情になる（=劇伴の変容原理）。
- `harmony` 省略時は旋法ごとのデフォルト進行が使われる。

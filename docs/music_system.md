# 音楽制作システム設計書 — 理論based劇伴パイプライン

> **何を語るか（物語）**: `content_design.md`（感情アークを音楽と共有）
> **どう描くか（映像）**: `architecture.md`
> **どう奏でるか（本書）**: 理論で設計し精密にレンダリングする劇伴システム

---

## 0. 核心思想：設計された理論 ≫ ランダム生成

動画が「ランダム動画生成」を捨て「静止画＋深度パララックス」で**設計し精密に動かした**のと同じ。
音楽も「ランダム text-to-music」を核にしない。**理論で書いたスコアが背骨、AIは質感の絵の具**。

| 動画パイプライン | 音楽パイプライン |
|---|---|
| content_design.md（感情アーク）| **共有** |
| 静止画（設計素材）| **MIDIスコア（music21で理論設計）** |
| 深度→パララックス（精密な動き）| **SoundFont→精密レンダリング** |
| compositor（グレード/グレイン）| **ミックス/マスタリング（EQ/reverb/-16 LUFS）** |
| LTX-Video（hero shotのみAI）| **AI音楽（テクスチャ/アンビエンスのみ）** |
| クリップベース（シーン=独立MP4）| **キューベース（章=独立音楽片）** |
| 視覚モチーフ反復（christus_victor）| **ライトモチーフ反復（勝利の主題）** |

### 確定した方針（2026-06-05）
1. **AIの役割** = 理論核 + AI質感アクセントのみ
2. **主題作曲** = 理論システムに委任（Claudeが神学的意味から設計・提案、採否は人間）
3. **実音化** = 高品質SoundFont から開始（無料・決定的・制御可）

---

## 1. ライトモチーフ体系（理論の心臓）

神学的意味を持つ少数の動機を **音度（スケール度数）** で定義する。
絶対音高でなく度数で持つので、調・旋法を変えるだけで**同じ動機が別の感情に変容**する。
これが劇伴（film scoring）の正統手法であり「理論based」の核。

| モチーフ | 神学的意味 | 性格 | 度数の骨子 |
|---|---|---|---|
| **victory** | Christus Victor・勝利 | 上行・英雄的・開放 | 1→5→8→10（完全音程の上昇＝勝利） |
| **bondage** | 恐れ・罪悪感の反復 | 狭い・執拗・短二度 | 1→♭2→1→7（強迫的に circling） |
| **shalom** | 創造・祝福・平和 | 広い・協和・穏やか | 1→3→5→8（長三和音の開放） |
| **question** | 問い・神秘 | 未解決・浮遊 | 5→6→7→♯4（リディア＝驚異、解決しない） |

### 変容（motif_treatment）
- **fragmented**: 冒頭2〜3音のみ・疎ら（闇の中で主題が断片化）
- **searching**: 短調・遅く・低く・弱く（解放前の探求）
- **triumphant**: 全奏・高く・強く・短調由来ならピカルディ終止で長三度に開く（勝利）
- **full**: 完全な提示

### 旋法と感情のマッピング
| 旋法 | 感情 | 用途 |
|---|---|---|
| ionian（長）| 喜び・確信 | 祝福・解放・勝利 |
| aeolian（短）| 哀しみ・喪失 | 滅・警告 |
| dorian | 古雅・希望含みの短 | 異教の神秘・改革前夜 |
| phrygian | 恐れ・緊張 | 砕く・束縛 |
| lydian | 驚異・超越 | 問い・神の視点 |
| mixolydian | 力強い古代 | 文明の栄華 |

---

## 2. キュー（音楽片）スキーマ — `music_schema.md` 参照

各章 = 1キュー。`cues/<章>.json` が `scenes/<章>.json` と並行する。

```jsonc
{
  "id": "ch6_reformation",
  "duration": 90.0,
  "key": "D",
  "mode": "dorian",            // 旋法
  "tempo": 72,
  "emotion": "breakthrough",
  "motif": "victory",          // ライトモチーフ参照
  "motif_treatment": "triumphant",
  "instrumentation": ["strings", "organ", "low_brass"],
  "dynamic_arc": "build",      // swell|build|sustain|decay
  "harmony": "i-VII-III-VII-i",// ローマ数字（任意・旋法和声）
  "texture_layer": {           // AI質感（任意・Colab）
    "prompt": "sacred reverberant choir pad, distant",
    "gain": 0.18
  }
}
```

---

## 3. OSSスタック（無料・Colab）

| 役割 | 第一候補 | フォールバック | 実行場所 |
|---|---|---|---|
| 作曲・和声理論 | **music21**（MIT）| 手書きMIDI | ローカル（純Python）|
| MIDI操作 | pretty_midi / mido | music21 | ローカル |
| スコア→音声（基盤）| **FluidSynth + orchestral SoundFont** | 簡易SF2 | Colab |
| 音響効果 | **pedalboard**（reverb/EQ/comp）| — | Colab |
| ラウドネス | **pyloudnorm**（-16 LUFS）| ffmpeg loudnorm | Colab |
| AIテクスチャ（任意）| Stable Audio Open | 無し（純管弦）| Colab(GPU) |
| AI実音化（将来）| ACE-Step（track単位）| SoundFontのまま | Colab(GPU) |

役割分担は動画と同じ：**ローカル=理論設計/MIDI生成、Colab=重いレンダリング**。

---

## 4. レンダリング/レコーディングの流れ（キューベース）

```
1キューごとに（章単位）:
  ① 理論設計 → MIDI（music21・ローカル）
     - 旋法/調/テンポ設定、和声進行、ライトモチーフを treatment 適用して配置
     - 楽器ごとにトラック分離（=マルチトラック録音の素）
  ② MIDI → ステム音声（Colab）
     - FluidSynth + SoundFont で楽器別 wav（strings.wav, organ.wav...）
  ③ ミックス（Colab・pedalboard）
     - 楽器別 EQ / パン / リバーブ（空間）/ コンプ
     - AIテクスチャ層を薄く重ねる（任意）
  ④ マスタリング（Colab・pyloudnorm）
     - -16 LUFS 正規化（content_design要件）/ リミッタ
全キュー結合 → 作品BGMトラック → ナレーション/SEと統合（renderer）
```

「ステム分離→ミックス→マスタリング」は実際のレコーディング工程の再現。
"適当な一発生成"ではなく、各楽器を設計し空間に配置する。

---

## 5. ミッション整合・美学

- **厳粛・知的・映画的**（content_designのトーン）。派手な展開・EDM的高揚は排除。
- ナレーションを邪魔しない：BGMは中域を空け（EQで-3dB帯域）、ナレ区間はダッキング。
- 「砕く」SE＝低域インパクト+ブラス（勝利の打撃）。music systemのSE層で設計。
- 主題は作品の神学（Christus Victor）を音で体現する。音楽自体が説教になる。

---

## 6. Phaseロードマップ

| Phase | 内容 | 場所 |
|---|---|---|
| **MP1** | ライトモチーフ定義 + composer（cue→MIDI）| ローカル ✅実装中 |
| **MP2** | Colab: FluidSynth レンダリング + pyloudnorm マスタリング | Colab |
| **MP3** | pedalboard マルチトラック・ミックス（ステム→空間配置）| Colab |
| **MP4** | content_designの全章感情アークから全キュー設計 | ローカル |
| **MP5** | AIテクスチャ層（Stable Audio Open）重ね | Colab(GPU) |
| **MP6** | ナレーション+BGM+SE 統合（rendererと結合・-16 LUFS）| Colab |

---

## 7. スケール設計

- キュー仕様（JSON）は作品非依存 → 別ドキュメンタリーも同じシステムで作曲
- ライトモチーフ集は作品ごとに定義（作品の神学/主題に対応）
- 「どの旋法・どの動機が感情に効くか」の知見が作品をまたいで蓄積

# 技術調査・設計判断（2026年5月）

> このドキュメントは「なぜこの構成にしたか」を残すもの。
> 前プロジェクト `blessing_documentary` の反省と、2026年5月時点の実地調査に基づく。

---

## 結論（先に答え）

**前回案（SDXL + SadTalker + Wan + Blender）は破棄。**
**新方針：2.5Dパララックス中心 + 高品質AI静止画 + シネマ後処理。**

理由を一言で言うと：

> ドキュメンタリーは「動画生成」を必要としていない。
> 「静止画に立体的な動き」を与えれば、Apple TV のドキュメンタリー級になる。
> しかもそれは**桁違いに速く・安く・制御可能**。

---

## 調査で分かった2026年の技術地形

### 1. 画像生成：FLUX.1 が品質トップ、だが T4 では要量子化

| モデル | 品質 | T4(15GB)で動くか | 速度 |
|---|---|---|---|
| **FLUX.1 [schnell]** | ★★★★★ | △ NF4量子化で可（~6-8GB） | schnellは4ステップで高速 |
| FLUX.1 [dev] | ★★★★★ | △ 量子化必須 | 遅い |
| SDXL | ★★★★ | ✅ 余裕（8GB） | 速い・LoRA資産豊富 |

**判断：** FLUX.1 schnell（NF4量子化）を第一候補、SDXL をフォールバックに。
両者を同一インターフェースの裏に隠し、環境に応じて自動選択。

→ [BentoML: Open-Source Image Models 2026](https://www.bentoml.com/blog/a-guide-to-open-source-image-generation-models)
→ [Flux vs SDXL 2026](https://pxz.ai/blog/flux-vs-sdxl)

---

### 2. ★最重要★ 2.5Dパララックス：これが今回の主役

静止画を「奥行きのある立体カメラ移動」に変える技術。
平面的なケンバーンズ（前回）とは別次元の没入感。

**パイプライン：**
```
静止画 → Depth Anything V2（深度推定）→ DepthFlow（パララックス生成）→ 動くクリップ
```

| ツール | 方式 | 速度 | 穴埋め品質 | 採用 |
|---|---|---|---|---|
| **DepthFlow** | GPUシェーダー変位 | ★★★★★ 最速・バッチ向き | 良 | ✅ 第一候補 |
| 3d-ken-burns (sniklaus) | メッシュ+インペイント | ★★ 遅い | ★★★ 最高 | hero shot用 |
| 3d-photo-inpainting | レイヤー深度 | ★ 遅い | ★★★ | 不採用（重い） |
| **自前 grid_sample** | PyTorch変位 | ★★★★ | 並（境界padding） | ✅ 依存ゼロのフォールバック |

**なぜパララックスが「タイパ最強」か：**
- 1ショット数秒で生成（動画生成は数分）
- 決定論的（プロンプトガチャがない）
- T4で余裕
- 既存画像にもAI生成画像にも効く
- これ単体で映像が「高級」に見える

→ [Depth Anything V2](https://depth-anything-v2.github.io/)
→ [DepthFlow (BrokenSource)](https://github.com/BrokenSource/DepthFlow)
→ [3d-ken-burns (sniklaus)](https://github.com/sniklaus/3d-ken-burns)

---

### 3. テキスト動画生成：脇役に降格（hero shotのみ）

| モデル | 品質 | 必要VRAM | T4で動くか |
|---|---|---|---|
| **LTX-Video** | ★★★ | 12GB | ✅ 唯一余裕 |
| Wan 2.1 1.3B | ★★★★ | 16GB | △ ギリギリ |
| Wan 2.2 14B | ★★★★★ | 24GB+ | ❌ |
| HunyuanVideo | ★★★★★ | 24GB+ | ❌ |

**判断：** 動画生成は**キー場面の3〜5秒だけ**に限定し LTX-Video を使う。
全編に使うのは遅すぎ・制御不能・T4で重い。蒸気機関が動く瞬間など「ここぞ」だけ。

→ [Wan2.2 vs HunyuanVideo vs LTXVideo 2026](https://www.aimagicx.com/blog/open-source-ai-video-models-comparison-2026)
→ [Image-to-Video on GPU Cloud 2026](https://www.spheron.network/blog/image-to-video-gpu-cloud-ltx-wan-hunyuan/)

---

### 4. ナレーション：edge-tts → Style-Bert-VITS2 へ格上げ

前回の edge-tts は無料だが機械的。日本語ナレーションの質が動画の格を決める。

**Style-Bert-VITS2（litagin02）** が日本語コミュニティで「無料最高峰」の定評。
- 日本語のピッチアクセント・イントネーションを正確に処理
- 感情・スタイル制御可能
- Colab対応・APIコストゼロ
- 音声クローンも可能（将来、専用ナレーター音声を作れる）

**判断：** Style-Bert-VITS2 を第一候補、edge-tts をフォールバックに。

→ [Style-Bert-VITS2 GitHub](https://github.com/litagin02/Style-Bert-VITS2)
→ [Style-Bert-VITS2 入門 (zenn)](https://zenn.dev/litagin/articles/style-bert-vits2-intro)

---

### 5. 「肖像画を喋らせる」（SadTalker）は核心から除外

前回案の目玉だったが、**神学ドキュメンタリーには逆効果**と判断。

- ルターの口が動く映像は容易に「安っぽい・不気味」になり、荘厳さを損なう
- 代わりに：肖像画を**パララックスで微妙に動かし**、大気光・粒子を重ね、
  ナレーター（SBV2）が語る方が、上品で・安く・確実

→ SadTalker は **オプションモジュール**として残すが、デフォルトでは使わない。

---

## 新アーキテクチャの全体像

```
スクリプト（script_proto相当）
    ↓
シーン定義 JSON（宣言的）
    ↓
┌─ アセット生成層（キャッシュ・冪等）──────────────┐
│  image_gen.py    : FLUX schnell / SDXL で背景静止画   │
│  depth_parallax  : Depth Anything V2 → DepthFlow      │
│  narration.py    : Style-Bert-VITS2 で音声           │
│  video_gen.py    : LTX-Video（hero shotのみ）         │
└──────────────────────────────────────────────────────┘
    ↓
compositor.py（GPU後処理）
  カラーグレード + ビネット + フィルムグレイン
  + 大気粒子 + テキスト合成 + フェード
    ↓
renderer.py（ffmpeg NVENC でクリップ出力 → 結合）
    ↓
build/output/video_full.mp4
```

### 設計の3原則

1. **クリップベース**：各シーンは独立したMP4クリップを生成 → 後処理 → 結合。
   （前回の「全フレームをPythonで積む」モデルより、各最新ツールと相性が良い）

2. **段階的フォールバック**：全層が環境に応じて劣化動作する。
   - GPU無 → CPU
   - FLUX無 → SDXL → 既存画像
   - DepthFlow無 → 自前 grid_sample パララックス → ケンバーンズ
   - SBV2無 → edge-tts

3. **キャッシュ冪等**：画像・深度・音声は `cache_key` で再生成スキップ。
   同じシーンを何度レンダしても無駄な計算をしない。

---

## VRAM 予算（Colab T4: 15GB、順次実行）

| 処理 | VRAM | 備考 |
|---|---|---|
| FLUX schnell (NF4) | ~7GB | 順次・終わったら解放 |
| Depth Anything V2 Small | ~1GB | 軽量 |
| DepthFlow | ~1GB | シェーダー |
| Style-Bert-VITS2 | ~2GB | |
| LTX-Video | ~12GB | hero shot時のみ単独実行 |
| compositor | ~2GB | |

→ **モデルは順次ロード・実行・解放**。同時に載せない設計が鍵。

---

## 前回からの移行

- `blessing_documentary/assets/images/` の21枚はそのまま再利用可（パララックス化で蘇る）
- `gen_narration.py` のセグメント構造 → `narration.py` に概念移植
- `script_proto.py` のセグメント → scene_schema JSON に変換

---

## タイパ評価（前回 vs 今回）

| 項目 | 前回(CPU moviepy) | 今回(GPU新設計) |
|---|---|---|
| 25分動画レンダ | 60〜90分 | 10〜20分 |
| 映像の質感 | スライドショー的 | シネマ的（奥行き・大気） |
| 1ショットの動き生成 | ケンバーンズのみ | 立体パララックス |
| プロンプトガチャ | なし | 静止画のみ（動きは決定論的） |
| 再利用性 | 低 | 高（汎用テンプレ） |

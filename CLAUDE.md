# Documentary GPU Pipeline

次世代ドキュメンタリー自動制作パイプライン。
前プロジェクト `blessing_documentary`（CPU・moviepy・スライドショー的）の反省を踏まえ、
**2.5Dパララックス中心 + 高品質AI静止画 + シネマ後処理**で再設計したGPUネイティブ基盤。

> **何を作るか（コンテンツ）**: `docs/content_design.md` ← 引越し完了・ここが出発点
> **どう作るか（技術）**: `docs/research_2026.md` / `docs/architecture.md`
> **前作の教訓**: `docs/lessons_from_v31.md`

---

## このプロジェクトの核心思想

> ドキュメンタリーに「動画生成」は要らない。
> **静止画に立体的な奥行きの動きを与える**だけで、別次元の没入感になる。
> それは桁違いに速く・安く・制御可能。

前回の「あらゆるAIモデルを投入」案は破棄した。今回は引き算の設計。

---

## スタック（2026年5月時点の最適解）

| 役割 | 第一候補 | フォールバック | 根拠 |
|---|---|---|---|
| 背景静止画 | FLUX.1 schnell (NF4量子化) | SDXL → 既存画像 | T4で品質トップ |
| **立体的な動き** | **Depth Anything V2 → DepthFlow** | 自前grid_sample → ケンバーンズ | **今回の主役** |
| ナレーション | Style-Bert-VITS2 | edge-tts | 日本語無料最高峰 |
| hero動画(数秒のみ) | LTX-Video | 静止画パララックス | T4で唯一余裕 |
| 後処理合成 | PyTorch (GPU) | — | グレード/グレイン/粒子/テキスト |
| エンコード | ffmpeg h264_nvenc | libx264 | GPU encode |

**SadTalker（肖像画を喋らせる）は核心から除外。** 神学ドキュメンタリーには不気味で逆効果。
肖像はパララックス＋大気光で上品に動かす。SadTalkerはオプション扱い。

---

## フォルダ構成

```
documentary_gpu/
├── CLAUDE.md              # このファイル（起動時の文脈）
├── QUICKSTART.md          # 最初に何をするか
├── requirements.txt       # 依存ライブラリ
├── docs/
│   ├── research_2026.md   # ★技術調査・設計判断の根拠
│   ├── architecture.md    # データフロー詳細
│   └── scene_schema.md    # シーン定義フォーマット
├── src/
│   ├── renderer.py        # クリップベース統括 + ffmpegパイプ
│   ├── depth_parallax.py  # ★主役: 深度推定→パララックス
│   ├── image_gen.py       # FLUX schnell / SDXL ラッパー
│   ├── narration.py       # Style-Bert-VITS2 / edge-tts
│   ├── compositor.py      # GPU後処理（グレード/グレイン/粒子/テキスト）
│   ├── video_gen.py       # LTX-Video（hero shot）
│   └── character.py       # SadTalker（オプション・非推奨）
├── scripts/
│   ├── pipeline.py        # メインCLI
│   ├── colab_render.ipynb # Colabノートブック
│   └── make_scenes.py     # スクリプト→シーンJSON変換
├── scenes/                # シーン定義JSON（章ごと）
├── assets/{images,bgm,characters}/
├── build/{audio,depth,clips,chapters,output}/
└── models/                # weightsキャッシュ（git管理外）
```

## レンダリングの流れ（クリップベース）

各シーンは独立クリップを生成 → 後処理 → 結合。前回の「全フレームPython積み」より各ツールと相性が良い。

```
1シーンごとに:
  ① ベース動きクリップを生成
     - parallax : Depth Anything V2(深度) → DepthFlow(動き) → mp4
     - video    : LTX-Video → mp4
     - title    : GPU生成グラデーションフレーム → mp4
  ② GPU後処理（compositor）
     - カラーグレード / ビネット / フィルムグレイン / 大気粒子
     - テキスト合成（PIL→tensor）/ フェード
  ③ 音声を結合（ナレーション + BGM + SE）
全シーン結合 → 最終MP4
```

## 設計3原則

1. **クリップベース** — シーン=独立MP4。最新ツール（DepthFlow/LTX）と素直に繋がる。
2. **段階的フォールバック** — GPU無→CPU、FLUX無→SDXL→既存画像、DepthFlow無→自前parallax→ケンバーンズ、SBV2無→edge-tts。どの環境でも止まらない。
3. **キャッシュ冪等** — 画像/深度/音声は `cache_key` で再生成スキップ。

## VRAM予算（T4 15GB、順次ロード・解放が鉄則）

FLUX schnell ~7GB / DepthAnythingV2 ~1GB / DepthFlow ~1GB / SBV2 ~2GB / LTX ~12GB(単独) / compositor ~2GB
→ **同時に載せない**。各モデルは使い終わったら `del` + `torch.cuda.empty_cache()`。

## 開発ロードマップ

- **Phase 1（基盤）**: renderer / compositor / depth_parallax の自前フォールバックを完成 → 既存21枚で動作確認
- **Phase 2（AI画像）**: image_gen に FLUX schnell 統合、Colab T4で確認
- **Phase 3（音声格上げ）**: narration を Style-Bert-VITS2 に
- **Phase 4（hero動画）**: video_gen に LTX-Video
- **Phase 5（パイプライン完成）**: pipeline.py 統括、Colabノートブック、blessing次作で実運用

## 前回プロジェクトとの接続

- `blessing_documentary/assets/images/`（21枚）→ そのまま `assets/images/` にコピーで再利用可
- `gen_narration.py` のセグメント構造 → `narration.py` に移植
- `script_proto.py` → `scripts/make_scenes.py` で scene JSON に変換

## 起動方法

```bash
cd documentary_gpu
python scripts/pipeline.py status
python scripts/pipeline.py render --chapter ch1
```

## 注意

- weights は `models/`（git管理外）
- Colabでは Drive の `documentary_gpu_assets/` を参照
- モデルの同時ロード厳禁（VRAM）

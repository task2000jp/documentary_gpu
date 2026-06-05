# アーキテクチャ（クリップベース）

## データフロー

```
scenes/<章>.json（宣言的シーン定義）
        │
        ▼  pipeline.py render <章>
┌──────────────────────────────────────────────┐
│ renderer.render_chapter()                      │
│   各シーンについて render_scene():              │
│                                                │
│   ① _base_clip()  ベース動きクリップ生成        │
│      ├ parallax → depth_parallax.animate()     │
│      │    Depth Anything V2 → DepthFlow         │
│      │    （無ければ grid_sample → ケンバーンズ）│
│      ├ gradient → GPU生成（タイトル）           │
│      └ video    → video_gen（LTX, hero shot）   │
│                                                │
│   ② _postprocess()  GPU後処理                   │
│      compositor: grade→vignette→atmosphere      │
│                  →grain→text→fade               │
│                                                │
│   ③ _mux_audio()  ナレーション結合              │
│                                                │
│   → build/clips/<id>.mp4                        │
│                                                │
│   全シーンを ffmpeg concat                      │
│   → build/chapters/<章>.mp4                     │
└──────────────────────────────────────────────┘
```

## フレーム後処理の中身（compositor）

```
ベースクリップを ffmpeg で raw rgb24 にデコード
  → 1フレームごとに GPU tensor 化
    color_grade   カラートーン（warm/cold/sepia）
    vignette      周辺減光
    atmosphere    大気粒子（任意）
    film_grain    フィルムグレイン
    overlay_text  日本語テキスト（PIL→tensor）
    fade          シーン内フェード
  → ffmpeg で再エンコード（NVENC）
```

## モデルのVRAM運用（T4 15GBで詰まらせない・順次ロード/解放が鉄則）

各モデルの実サイズ（同時に載せない）:
FLUX schnell ~7GB / DepthAnythingV2 ~1GB / DepthFlow ~1GB / SBV2 ~2GB /
LTX ~12GB(単独) / compositor ~2GB → 使い終わったら `del` + `torch.cuda.empty_cache()`。

```
画像生成フェーズ : image_gen.generate_background() ×N → image_gen.free()
深度フェーズ     : depth_parallax で順次 → free_depth_model()
音声フェーズ     : narration.synthesize() ×N → narration.free()
hero動画        : video_gen.generate()（単独実行）→ video_gen.free()
```
→ アセットを**先に全部生成・キャッシュ**してから、レンダリング段でGPUを軽く使う設計が安全。

## スタック（2026年5月時点の最適解）

| 役割 | 第一候補 | フォールバック | 根拠 |
|---|---|---|---|
| 背景静止画 | FLUX.1 schnell (NF4) | SDXL → 既存画像 | T4で品質トップ |
| 立体的な動き | Depth Anything V2 → DepthFlow | grid_sample → ケンバーンズ | 今回の主役 |
| ナレーション | Style-Bert-VITS2 | edge-tts | 日本語無料最高峰 |
| hero動画(数秒) | LTX-Video | 静止画パララックス | T4で唯一余裕 |
| 後処理合成 | PyTorch (GPU) | — | グレード/グレイン/粒子/テキスト |
| エンコード | ffmpeg h264_nvenc | libx264 | GPU encode |

**SadTalker（肖像を喋らせる）は核心から除外**（神学ドキュメンタリーには不気味）。肖像はパララックス＋大気光で上品に。

## 動画パイプラインのロードマップ

- Phase1（基盤）: renderer/compositor/depth_parallax の自前フォールバック → 既存画像で確認 ✅実証
- Phase2（AI画像）: image_gen に FLUX schnell 統合 🟡準備済
- Phase3（音声）: narration を Style-Bert-VITS2 に 🔴未
- Phase4（hero動画）: video_gen に LTX-Video 🔵スタブ
- Phase5（統合）: pipeline.py 統括・最終MP4（映像+ナレ+BGM+SE・-16 LUFS）🔴未

## 音声

```
Style-Bert-VITS2（or edge-tts）→ build/audio/<seg_id>.wav
  ＋ assets/bgm/*.mp3
  → 各シーンの _mux_audio で結合（章結合後に全体BGMを重ねてもよい）
```

## フォールバック連鎖（どの環境でも止まらない）

```
GPU      : CUDA → CPU
画像生成  : FLUX schnell → SDXL → 既存画像
パララックス: DepthFlow → grid_sample → （実質ケンバーンズ）
深度      : Depth Anything V2 → 放射状擬似深度
ナレーション: Style-Bert-VITS2 → edge-tts
動画生成  : LTX-Video →（呼ばない/parallaxで代替）
エンコード : h264_nvenc → libx264
```

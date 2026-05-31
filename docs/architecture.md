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

## モデルのVRAM運用（T4で詰まらせない）

```
画像生成フェーズ : image_gen.generate_background() ×N → image_gen.free()
深度フェーズ     : depth_parallax で順次 → free_depth_model()
音声フェーズ     : narration.synthesize() ×N → narration.free()
hero動画        : video_gen.generate()（単独実行）→ video_gen.free()
```
→ アセットを**先に全部生成・キャッシュ**してから、レンダリング段でGPUを軽く使う設計が安全。

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

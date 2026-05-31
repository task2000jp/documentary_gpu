# シーン定義スキーマ（クリップベース新設計）

シーンは JSON 配列。各要素が1クリップになる。`scenes/*.json` に章ごと保存。

## 基本構造

```jsonc
{
  "id": "ch6_luther_door",   // 一意ID（= 音声seg_idと揃えると楽）
  "duration": 12.0,           // 秒（通常 narration長 + padding）
  "background": { ... },      // 背景＝動きの素
  "audio": "build/audio/c6_2.wav",  // ナレーション（省略可）
  "text": { ... },            // テキストオーバーレイ（省略可）
  "grade": "warm",            // カラーグレード: warm|cold|sepia|neutral
  "vignette": 0.35,           // 周辺減光 0..1
  "grain": 0.03,              // フィルムグレイン
  "atmosphere": 0.0,          // 大気粒子 0..1（0でスキップ）
  "fade_in": 0.5, "fade_out": 0.5
}
```

## background タイプ

### parallax / image（★標準）— 既存画像を立体的に動かす
```jsonc
{
  "type": "image",
  "path": "assets/images/luther_wittenberg.jpg",
  "motion": "orbit",      // orbit|dolly|pan_lr|zoom_in
  "amplitude": 0.045      // 0.02〜0.06 が自然
}
```

### sd_generated — AI生成画像を立体的に動かす
```jsonc
{
  "type": "sd_generated",
  "prompt": "Martin Luther nailing 95 theses to church door, dramatic light",
  "style": "historical_oil",   // historical_oil|cinematic|documentary|epic_landscape
  "cache_key": "luther_door",  // 再生成スキップ用
  "motion": "dolly",
  "amplitude": 0.04
}
```

### gradient — タイトル用の単色グラデーション
```jsonc
{ "type": "gradient", "colors": ["#1a0a0a", "#3a1a1a"] }
```

### video_generated — LTX-Video（hero shotのみ・数秒）
```jsonc
{
  "type": "video_generated",
  "prompt": "steam engine piston moving, cinematic, industrial revolution"
}
```

## text タイプ
```jsonc
{ "content": "一五一七年　宗教改革", "style": "title" }
// style: title|subtitle|caption|quote
```

## 完全な章の例（scenes/ch6.json）

```json
[
  {
    "id": "ch6_title",
    "duration": 4.0,
    "background": {"type": "gradient", "colors": ["#1a0a0a", "#3a1a1a"]},
    "text": {"content": "第六章　宗教改革", "style": "title"},
    "grade": "sepia", "vignette": 0.5, "grain": 0.04,
    "fade_in": 0.8, "fade_out": 0.6
  },
  {
    "id": "ch6_luther_door",
    "duration": 12.0,
    "background": {
      "type": "image",
      "path": "assets/images/luther_wittenberg.jpg",
      "motion": "dolly", "amplitude": 0.04
    },
    "audio": "build/audio/c6_2.wav",
    "text": {"content": "一五一七年十月三十一日", "style": "subtitle"},
    "grade": "warm", "vignette": 0.4, "grain": 0.03, "atmosphere": 0.15
  }
]
```

## 設計メモ
- `id` を音声 `seg_id` と一致させると `audio` パスが自動で組める。
- `cache_key` を付けた sd_generated は2回目以降タダ（キャッシュ）。
- `motion` は画の内容で選ぶ：人物=dolly/orbit、風景=pan_lr/zoom_in。

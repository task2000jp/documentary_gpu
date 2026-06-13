# シーン定義スキーマ（クリップベース新設計）

シーンは JSON 配列。各要素が1クリップになる。`scenes/*.json` に章ごと保存。

> **scenes/*.json は通常 手書きしない。** 上流の `scenarios/<章>.json`（章の設計＝beat列）を
> `pipeline.py scenario <章>` でコンパイルして生成する。下記は生成される側の仕様。
> シナリオ機構の仕様は本書末尾「シナリオ→絵コンテ機構」を参照。

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
  "negative": "...",           // 任意: SDXL否定文を上書き。省略時 styleで自動
  "motion": "dolly",
  "amplitude": 0.04
}
// 否定文の自動選択(SDXLフォールバック時): historical_oil のみ
// "modern/contemporary/anachronistic" を除外。現代・実写styleでは付けない。
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

### manim — 図解アニメのヒーローカット（背骨/アダプタ/接続図）
```jsonc
{ "type": "manim", "scene": "AdapterSpine" }  // src/manim_scenes.py の Scene クラス名
```
Manim が自前で 1920x1080@24 の mp4 を生成 → 後段で grade/text を被せる。
依存: `pip install manim` + apt `libcairo2-dev libpango1.0-dev`（manimカット使用時のみ）。

## graphics — ベクター図解の重ね層（★線・図形をアニメ描画）

`background` と独立。実写(FLUX)やグラデの上に、線/ノード/データ流を時間で動かす。
座標・寸法は 0..1 正規化（x=幅, y=高, r=高さ基準, box w/h=幅/高基準）。追加依存なし。

```jsonc
"graphics": [
  {"type": "node", "at": [0.18,0.5], "shape": "circle", "r": 0.06,
   "label": "設備機器", "pulse": true, "appear": [0.2,0.9]},
  {"type": "node", "at": [0.82,0.5], "shape": "box", "w": 0.2, "h": 0.16,
   "label": "背骨", "color": [0,200,255]},
  {"type": "link", "from": [0.25,0.5], "to": [0.70,0.5],
   "draw": [0.9,2.2], "flow": true, "arrow": true,
   "color": [255,200,90], "label": "アダプタ"},
  {"type": "label", "at": [0.5,0.12], "text": "API", "size": 32}
]
```
- `appear:[t0,t1]` フェードイン窓 / `draw:[t0,t1]` 線が0→1で伸びる窓
- `flow:true` 線上を光点が流れる（=データ）/ `arrow:true` 矢頭（=制御の向き）/ `pulse:true` 脈動
- z順: link(下) → node → label(上)。色は RGB 配列（省略時シアン）。

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

---

## シナリオ→絵コンテ機構（`scripts/build_scenario.py`）

「シナリオをレンダリングする機構」の入口。**章の設計(beat列)** を書けば、尺の自動決定・
検証・schema準拠の `scenes/<章>.json` 生成までを純Python(torch不要)で行う。

```bash
python scripts/pipeline.py scenario <章>            # scenarios/<章>.json → scenes/<章>.json
python scripts/pipeline.py scenario <章> --render   # 生成して続けて描画（要torch=Colab）
```

### 入力 `scenarios/<章>.json`
```jsonc
{
  "chapter": "ch_x",
  "defaults": { "grade": "warm", "style": "cinematic", "voice_wps": 7.0 },
  "music": "cues/knopfler_anthem.json",   // 任意（BGMは pipeline.py music で別途焼く）
  "beats": [
    { "id":"t", "kind":"title",  "text":"第○章", "colors":["#0a0a12","#15152e"] },
    { "id":"a", "kind":"prompt", "prompt":"...", "style":"cinematic", "motion":"pan_lr",
      "text":"字幕", "narration":"原稿（文字数→尺を自動算出）", "grade":"cold",
      "graphics":[ ... ] },                // 図解の重ね層（上記 graphics 節）
    { "id":"i", "kind":"image",  "image":"foo.jpg", "motion":"orbit", "text":"..." },
    { "id":"h", "kind":"manim",  "scene":"AdapterSpine", "duration":10, "text":"..." },
    { "id":"v", "kind":"video",  "prompt":"...", "duration":5 }
  ]
}
```

### kind → background 対応
| kind | 生成される background | 必須 |
|---|---|---|
| `title`/`gradient` | gradient（colors） | （colors任意・既定暗色） |
| `image` | image（assets/images/＜image＞） | `image` |
| `prompt` | sd_generated（FLUX/SDXL, cache_key=id） | `prompt` |
| `manim` | manim（src/manim_scenes.py のクラス） | `scene` |
| `video` | video_generated（LTX, hero shotのみ） | `prompt` |

### 機構の要点
- **尺の自動決定**: `duration`明示 > `narration`文字数÷`voice_wps`+余白 > 種別既定(title4s/その他6s)。
- **声は未構築でも止まらない**: `narration`がある beat に `audio: build/audio/<id>.wav` を**先回りで配線**。
  wavが無い間は無音で描画し、後でwavを置けば自動でmuxされる（ナレーション部門の受け皿）。
- **検証**（v3.1教訓を反映）: 必須フィールド欠落・id重複・未知kind・極端に短い尺を**コンパイル前後で検出**し、
  エラーなら scenes を書き出さない。
- `scenarios/_template.json` が全種別を網羅した雛形。コピーして中身を差し替える。

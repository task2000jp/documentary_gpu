# QUICKSTART — このフォルダだけで始める

> このプロジェクトは `blessing_documentary` とは独立。
> このフォルダで `claude` を起動すれば `CLAUDE.md` を読んで文脈を即把握できる。

## 0. まず読むもの（Claude も人間も）

1. `CLAUDE.md` — 全体方針とスタック
2. `docs/research_2026.md` — なぜこの構成なのか（調査の根拠）
3. `docs/scene_schema.md` — シーン定義の書き方

## 1. ローカルで最小動作確認（設計/コーディング用・torch不要）

```bash
cd documentary_gpu
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-local.txt   # torchは入れない
brew install ffmpeg                                # mac

.venv/bin/python scripts/pipeline.py status
.venv/bin/python scripts/pipeline.py doctor
```

ローカルは設計・シーンJSON・状態確認まで。
**パララックスの実レンダリングはGPUが要るのでColabで実行する**
（README先頭の「Open In Colab」バッジ → セル5で試写）。

## 2. 既存アセットを引き継ぐ

```bash
# 前プロジェクトの画像21枚を再利用（パララックスで蘇る）
cp ../blessing_documentary/assets/images/*.jpg assets/images/
cp ../blessing_documentary/assets/images/*.png assets/images/
cp ../blessing_documentary/assets/bgm/*.mp3 assets/bgm/
```

## 3. 最初のシーンを試す

`scenes/test.json` を作って1シーンだけレンダリング:

```json
[
  {
    "id": "test_luther",
    "duration": 6.0,
    "background": {
      "type": "image",
      "path": "assets/images/luther_wittenberg.jpg",
      "motion": "orbit",
      "amplitude": 0.045
    },
    "grade": "warm",
    "vignette": 0.4,
    "grain": 0.03,
    "text": {"content": "一五一七年、宗教改革", "style": "subtitle"},
    "fade_in": 0.6, "fade_out": 0.6
  }
]
```

→ これで「平面画像 → 立体パララックス + シネマグレード + テキスト」の
   1クリップができる。前回のケンバーンズとの差を体感するのが第一目標。

## 4. Colab で GPU フル機能（Phase 2以降）

`scripts/colab_render.ipynb` を Drive 経由で開く。
FLUX schnell / Style-Bert-VITS2 / LTX-Video は Colab T4 で動かす。

## 開発の順番

```
Phase 1: 既存画像 → パララックス + 後処理 が動く（ローカルCPUでOK）
   ↓
Phase 2: FLUX schnell でAI背景生成（Colab GPU）
   ↓
Phase 3: Style-Bert-VITS2 でナレーション格上げ
   ↓
Phase 4: LTX-Video で hero shot
   ↓
Phase 5: scripts/make_scenes.py で台本→シーンJSON自動変換、全自動化
```

## 重要な設計判断（忘れないこと）

- **パララックスが主役**。動画生成（LTX）は脇役（hero shotのみ）。
- **SadTalkerは使わない**（神学ドキュメンタリーには不気味）。
- **モデルは同時に載せない**（T4 VRAM）。使ったら `free()` で解放。
- **全層フォールバックあり**。どの環境でも止まらないのが設計の肝。

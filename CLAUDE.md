# Documentary GPU Pipeline

次世代ドキュメンタリー自動制作パイプライン（GPUネイティブ）。
作品: **勝利の福音 ── なぜ蒸気機関はスコットランドで生まれたか**（神学ドキュメンタリー）。

> このファイルは起動時の「受付」。詳細は各docを**必要時に**読む（起動トークン節約）。

## 3原則
1. **設計＋精密描画 ≫ ランダム生成**（静止画+深度パララックス／理論MIDI+SoundFont）
2. **無料縛り・MCP駆使・スケール設計**
3. **段階的フォールバック／キャッシュ冪等**（どの環境でも止まらない）

## 役割分担
ローカル(Claude)=設計・コーディング・MCP操作（**torch不要**） ／ Colab T4=重いGPUレンダリング

## 部門地図（詳細は各doc）
| 部門 | doc | 状態 |
|---|---|---|
| 🎬 動画 | `docs/architecture.md` `docs/scene_schema.md` | parallax🟢 / FLUX🟡 / LTX🔵 |
| 🎵 音楽 | `docs/music_system.md` `docs/music_schema.md` | MIDI🟢 / Knopfler試作🟡 |
| 📢 配信・SEO | `docs/marketing_system.md` | 投稿🟢 / メタ生成🟢 / Loop A,C🔵 |
| 📚 脚本・収集 | `docs/content_design.md` / `gas/` | 脚本🟢完成 / GAS収集🟢 |
| 🔴 未構築 | — | **ナレーション**（声）／**最終統合**（映像+音+声→1本） |

技術背景: `docs/research_2026.md` ／ 前作の教訓: `docs/lessons_from_v31.md`

## 地雷回避（full-precision・外すと事故る）
- **ローカルにtorch等GPUスタックを入れない**（Intel Mac非対応・描画はColab）。依存は `requirements-local.txt` / `requirements-colab.txt` 分離。
- **git push**: `gh`無し。`git -c credential.helper= push "https://x-access-token:${GITHUB_TOKEN}@github.com/task2000jp/documentary_gpu.git" main:main`（トークンURL埋込・remoteに残さない）。
- **VRAM**: T4でモデル同時ロード厳禁。順次 `free()` ＋ `empty_cache()`（`docs/architecture.md`）。
- **音声**: 全て -16 LUFS 正規化。
- **機密**: `.mcp.json` / `client_secret*` / `token_youtube.json` は gitignore 済（コミット禁止）。
- **groq-compound MCP**: 常用しない（413多発・非効率）。最新情報は直接WebSearch（メモリ参照）。

## 起動
```bash
.venv/bin/python scripts/pipeline.py status   # 制作状況
.venv/bin/python scripts/pipeline.py doctor   # 環境チェック
```
Colab: README先頭の「Open In Colab」バッジ → `scripts/colab_render.ipynb`（映像）/ `colab_music.ipynb`（音楽）

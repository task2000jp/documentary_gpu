# Documentary GPU Pipeline

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/task2000jp/documentary_gpu/blob/main/scripts/colab_render.ipynb)

次世代ドキュメンタリー自動制作パイプライン。
**2.5Dパララックス中心 + 高品質AI静止画 + シネマ後処理**のGPUネイティブ基盤。

> ドキュメンタリーに「動画生成」は要らない。
> **静止画に立体的な奥行きの動きを与える**だけで、別次元の没入感になる ── 桁違いに速く・安く・制御可能。

## ▶ Colabで動かす（GPUレンダリング）

上の **Open In Colab** バッジをクリック → **ランタイム → T4 GPU** を選択 → セルを上から実行。
コードと画像は `git clone` で自動取得されるので、すぐに試写まで進めます。

| セル | 内容 |
|---|---|
| 1 | コード取得（clone）+ Drive マウント |
| 2 | 依存インストール（Phase1は最小セット） |
| 3 | 環境チェック（`✅ CUDA: Tesla T4` を確認） |
| 4 | アセット取得（画像はclone済みなのでスキップ可・BGMのみDrive） |
| 5 | 単一シーン試写（パララックス確認） |
| 6 | 章まるごとレンダリング |
| 7 | 成果物を Drive へ保存 |

## 役割分担

- **ローカル（Claude）**: 設計・コーディング・シーンJSON・MCP操作（torch不要）
- **Colab T4**: 画像生成 / 深度 / パララックス / TTS / 動画 / GPU後処理

## ドキュメント

- `CLAUDE.md` — 全体方針とスタック（起動時の文脈）
- `QUICKSTART.md` — 最初に何をするか
- `docs/research_2026.md` — 技術調査・設計判断の根拠
- `docs/content_design.md` — 何を作るか（コンテンツ設計）
- `docs/scene_schema.md` — シーン定義フォーマット

## 環境セットアップ

```bash
# ローカル（軽量・設計/コーディング用。torchは入れない）
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-local.txt

# Colab（フルGPUスタック）→ ノートブックのセル2が自動実行
#   pip install -r requirements-colab.txt
```

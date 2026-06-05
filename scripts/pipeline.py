"""
pipeline.py — documentary_gpu パイプライン管理 CLI

  python scripts/pipeline.py status
  python scripts/pipeline.py render <章名>      # scenes/<章名>.json を描画
  python scripts/pipeline.py render-scene <json> <id>  # 単一シーン試写
  python scripts/pipeline.py doctor             # 環境チェック（GPU/モデル/ffmpeg）
"""
import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "src"))


def cmd_status(args):
    scenes_dir = BASE / "scenes"
    chap_dir = BASE / "build" / "chapters"
    print("=== Documentary GPU 制作状況 ===\n")
    jsons = sorted(scenes_dir.glob("*.json")) if scenes_dir.exists() else []
    if not jsons:
        print("  scenes/*.json がまだありません。")
        print("  → QUICKSTART.md の手順3でテストシーンを作成してください。")
        return
    for j in jsons:
        name = j.stem
        mp4 = chap_dir / f"{name}.mp4"
        if mp4.exists():
            mb = mp4.stat().st_size / 1024 / 1024
            print(f"  ✅ {name:<12} ({mb:.1f}MB)")
        else:
            n = len(json.loads(j.read_text()))
            print(f"  ❌ {name:<12} 未レンダリング（{n}シーン定義済み）")


def cmd_render(args):
    import renderer
    scenes_path = BASE / "scenes" / f"{args.chapter}.json"
    if not scenes_path.exists():
        print(f"エラー: {scenes_path} がありません")
        return
    scenes = json.loads(scenes_path.read_text())
    out_dir = BASE / "build" / "chapters"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = str(out_dir / f"{args.chapter}.mp4")
    print(f"[render] {args.chapter}: {len(scenes)}シーン → {out}\n")
    renderer.render_chapter(scenes, out)


def cmd_render_scene(args):
    import renderer
    scenes = json.loads(Path(args.json).read_text())
    scene = next((s for s in scenes if s["id"] == args.id), None)
    if scene is None:
        print(f"エラー: id={args.id} が {args.json} にありません")
        return
    out_dir = BASE / "build" / "clips"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[render-scene] {args.id} 試写")
    path = renderer.render_scene(scene, out_dir)
    print(f"完了: {path}")


def cmd_doctor(args):
    print("=== 環境チェック ===\n")
    # GPU
    try:
        import torch
        if torch.cuda.is_available():
            print(f"  ✅ CUDA: {torch.cuda.get_device_name(0)}")
            vram = torch.cuda.get_device_properties(0).total_memory / 1e9
            print(f"     VRAM: {vram:.1f}GB")
            print("  → Colab/GPU環境: レンダリング可能")
        else:
            print("  ⚠️  CUDA なし（CPUで動作・パララックスは遅い）")
    except ImportError:
        print("  ⚪ torch 未導入 → ローカル(設計/コーディング)環境")
        print("     レンダリングはColabで requirements-colab.txt を使用")
    # ffmpeg
    import shutil
    has_nvenc = False
    if shutil.which("ffmpeg"):
        import subprocess
        r = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True)
        has_nvenc = "h264_nvenc" in r.stdout
        print(f"  ✅ ffmpeg{'（NVENC利用可）' if has_nvenc else '（CPUエンコード）'}")
    else:
        print("  ❌ ffmpeg なし → brew install ffmpeg / apt install ffmpeg")
    # 各モデル
    for mod, label in [("transformers", "Depth Anything V2"),
                       ("diffusers", "FLUX/SDXL/LTX"),
                       ("depthflow", "DepthFlow(任意)"),
                       ("style_bert_vits2", "Style-Bert-VITS2"),
                       ("edge_tts", "edge-tts(fallback)")]:
        try:
            __import__(mod)
            print(f"  ✅ {label}")
        except ImportError:
            print(f"  ⚪ {label} 未導入")


def main():
    p = argparse.ArgumentParser(description="Documentary GPU Pipeline")
    sub = p.add_subparsers(dest="command")
    sub.add_parser("status")
    sub.add_parser("doctor")
    pr = sub.add_parser("render"); pr.add_argument("chapter")
    rs = sub.add_parser("render-scene")
    rs.add_argument("json"); rs.add_argument("id")

    args = p.parse_args()
    {"status": cmd_status, "render": cmd_render,
     "render-scene": cmd_render_scene, "doctor": cmd_doctor}.get(
        args.command, lambda a: p.print_help())(args)


if __name__ == "__main__":
    main()

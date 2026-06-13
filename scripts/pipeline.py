"""
pipeline.py — documentary_gpu パイプライン管理 CLI

  python scripts/pipeline.py status
  python scripts/pipeline.py scenario <章名>    # scenarios/<章>.json → scenes/<章>.json（絵コンテ生成）
  python scripts/pipeline.py render <章名>      # scenes/<章名>.json を描画
  python scripts/pipeline.py render-scene <json> <id>  # 単一シーン試写
  python scripts/pipeline.py music <cue>        # cue(JSON)→MIDI→WAV を1コマンドで（claw-daw方式）
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
    scenario_dir = BASE / "scenarios"
    print("=== Documentary GPU 制作状況 ===\n")
    scns = sorted(scenario_dir.glob("*.json")) if scenario_dir.exists() else []
    if scns:
        print("【シナリオ】scenarios/ → pipeline.py scenario <名>")
        for s in scns:
            compiled = (scenes_dir / f"{json.loads(s.read_text()).get('chapter', s.stem)}.json").exists()
            print(f"  {'🟢' if compiled else '⚪'} {s.stem:<14}{'（絵コンテ生成済）' if compiled else '（未コンパイル）'}")
        print()
    print("【絵コンテ/描画】scenes/ → pipeline.py render <名>")
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


def cmd_scenario(args):
    """シナリオ(scenarios/<章>.json) → 絵コンテ(scenes/<章>.json)。
    --render を付けると続けて描画（torch必須＝Colab）。"""
    import build_scenario
    try:
        out_path, scenes = build_scenario.build(args.scenario, args.out)
    except (FileNotFoundError, ValueError) as e:
        print(f"エラー: {e}")
        return
    if args.render:
        import renderer
        chapter = json.loads(Path(out_path).read_text())
        out_dir = BASE / "build" / "chapters"
        out_dir.mkdir(parents=True, exist_ok=True)
        scenario = build_scenario.load_scenario(args.scenario)
        out = str(out_dir / f"{scenario['chapter']}.mp4")
        print(f"\n[render] {len(chapter)}シーン → {out}\n")
        renderer.render_chapter(chapter, out)


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


def cmd_music(args):
    """cue(JSON) → MIDI → WAV を1コマンドで（claw-daw方式の "render project.json"）。

    MIDI作曲は純Python(music21)で常にローカル完結。
    WAV化(FluidSynth+ミックス+ -16 LUFS)は fluidsynth がある環境だけ続行し、
    無ければ MIDI を残して Colab(colab_music.ipynb) への引き渡しを案内する。
    """
    import shutil
    import subprocess
    from music import composer

    # cue 解決: パス指定 or cues/<名>.json
    cue_path = Path(args.cue)
    if not cue_path.exists():
        cand = BASE / "cues" / f"{args.cue}.json"
        if cand.exists():
            cue_path = cand
        else:
            print(f"エラー: cue が見つかりません: {args.cue}（cues/{args.cue}.json も無し）")
            return
    cue = json.loads(cue_path.read_text())
    cid = cue.get("id", cue_path.stem)
    style = args.style or cue.get("style", "orchestral")

    music_dir = BASE / "build" / "music"
    music_dir.mkdir(parents=True, exist_ok=True)
    midi = str(music_dir / f"{cid}.mid")
    wav = args.out or str(music_dir / f"{cid}.wav")

    # ① 作曲（理論based・ローカル）
    print(f"[music] {cid}: {cue.get('key','C')} {cue.get('mode','ionian')} "
          f"{cue.get('tempo',72)}BPM / 主題={cue.get('motif','victory')} "
          f"({cue.get('motif_treatment','full')}) / style={style}")
    composer.write_midi(cue, midi)
    print(f"  ① 作曲完了 → {midi}")

    # ② WAV化（FluidSynth がある環境＝Colab等のみ）
    if not shutil.which("fluidsynth"):
        print("  ⚪ fluidsynth 未導入（ローカル設計環境）→ MIDIまでで停止")
        print("     WAV化は Colab で: scripts/colab_music.ipynb（ランタイム→すべて実行）")
        print(f"     または fluidsynth のある環境で:"
              f" python scripts/render_music.py {midi} --out {wav} --style {style}")
        return
    cmd = [sys.executable, str(BASE / "scripts" / "render_music.py"),
           midi, "--out", wav, "--style", style]
    if args.soundfont:
        cmd += ["--soundfont", args.soundfont]
    subprocess.run(cmd, check=True)
    print(f"\n[music] 劇伴完成: {wav}")


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


def cmd_upload(args):
    import upload_youtube
    meta_path = Path(args.meta) if args.meta else None
    if meta_path is None:
        # --chapter 指定時はデフォルトメタを探す
        meta_path = BASE / "scenes" / f"{args.chapter}_meta.json"
    if not meta_path.exists():
        print(f"エラー: {meta_path} がありません。--meta でJSONを指定してください。")
        return
    video_path = args.video or str(BASE / "build" / "chapters" / f"{args.chapter}.mp4")
    if not Path(video_path).exists():
        print(f"エラー: {video_path} がありません。先に render を実行してください。")
        return
    meta = json.loads(Path(meta_path).read_text())
    from datetime import datetime
    schedule_dt = datetime.fromisoformat(args.schedule) if args.schedule else None
    upload_youtube.upload(video_path, meta, schedule_dt)


def main():
    p = argparse.ArgumentParser(description="Documentary GPU Pipeline")
    sub = p.add_subparsers(dest="command")
    sub.add_parser("status")
    sub.add_parser("doctor")
    sc = sub.add_parser("scenario", help="シナリオ→絵コンテ(scenes JSON)生成")
    sc.add_argument("scenario", help="scenarios/<名>.json か JSONパス")
    sc.add_argument("--out", default=None, help="出力 scenes JSON")
    sc.add_argument("--render", action="store_true", help="生成後そのまま描画（要torch=Colab）")
    pr = sub.add_parser("render"); pr.add_argument("chapter")
    rs = sub.add_parser("render-scene")
    rs.add_argument("json"); rs.add_argument("id")
    mu = sub.add_parser("music", help="cue(JSON)→MIDI→WAV を1コマンドで")
    mu.add_argument("cue", help="cues/<名>.json か JSONパス")
    mu.add_argument("--out", default=None, help="出力WAV（省略時 build/music/<id>.wav）")
    mu.add_argument("--style", default=None,
                    choices=["orchestral", "fingerstyle"],
                    help="ミックス（省略時はcueのstyle、無ければorchestral）")
    mu.add_argument("--soundfont", default=None, help="SoundFont(.sf2)パス")
    up = sub.add_parser("upload", help="YouTube にアップロード")
    up.add_argument("chapter", nargs="?", help="章名（build/chapters/<章>.mp4）")
    up.add_argument("--video",    default=None, help="動画ファイルを直接指定")
    up.add_argument("--meta",     default=None, help="メタデータJSON（省略時: scenes/<章>_meta.json）")
    up.add_argument("--schedule", default=None, help="予約投稿日時 ISO8601")

    args = p.parse_args()
    {"status": cmd_status, "scenario": cmd_scenario, "render": cmd_render,
     "render-scene": cmd_render_scene, "music": cmd_music,
     "doctor": cmd_doctor, "upload": cmd_upload}.get(
        args.command, lambda a: p.print_help())(args)


if __name__ == "__main__":
    main()

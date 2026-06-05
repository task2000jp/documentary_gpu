"""
optimize_images.py — アセット画像をドキュメンタリー用途に最適化

  python scripts/optimize_images.py [--max 2560] [--quality 90] [dir]

長辺を MAX px に縮小（拡大はしない）し再エンコード。
- パララックスの深度推定を高速化し、リポジトリ/転送を軽量化する。
- 元画像は blessing_documentary/assets/images/ にバックアップがある前提。
"""
import argparse
import sys
from pathlib import Path
from PIL import Image

EXTS = {".jpg", ".jpeg", ".png"}


def optimize(path: Path, max_edge: int, quality: int) -> tuple[int, int]:
    before = path.stat().st_size
    img = Image.open(path)
    w, h = img.size
    long_edge = max(w, h)
    if long_edge > max_edge:
        scale = max_edge / long_edge
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)

    # 一時ファイルに書き出して、元より大きくなったら破棄（既に高圧縮な画像対策）
    tmp = path.with_suffix(path.suffix + ".tmp")
    if path.suffix.lower() == ".png":
        img.save(tmp, "PNG", optimize=True)
    else:
        img.convert("RGB").save(tmp, "JPEG", quality=quality, optimize=True, progressive=True)

    if tmp.stat().st_size < before:
        tmp.replace(path)
    else:
        tmp.unlink()  # 元の方が小さい → 元を維持

    return before, path.stat().st_size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", nargs="?", default="assets/images")
    ap.add_argument("--max", type=int, default=2560, help="長辺の最大px")
    ap.add_argument("--quality", type=int, default=90, help="JPEG品質")
    args = ap.parse_args()

    base = Path(args.dir)
    files = sorted(f for f in base.iterdir() if f.suffix.lower() in EXTS)
    if not files:
        print(f"画像が見つかりません: {base}")
        sys.exit(1)

    total_b = total_a = 0
    for f in files:
        b, a = optimize(f, args.max, args.quality)
        total_b += b
        total_a += a
        print(f"  {f.name:<28} {b/1048576:6.1f}MB → {a/1048576:5.1f}MB")
    print(f"\n合計 {total_b/1048576:.1f}MB → {total_a/1048576:.1f}MB "
          f"（{100*(1-total_a/total_b):.0f}% 削減）")


if __name__ == "__main__":
    main()

"""Build every image the project needs from the one logo artwork.

The source is a flat mark - a pen nib with a flame in it - on a solid cream
ground. Nothing here redraws it. The only thing this script does to the artwork
is decide how much of each square it should occupy, because the source canvas
carries wide empty margins: pasted into a 32px icon untouched, the mark would be
a speck in the middle of a cream square.

  logo-600.png      the artwork as drawn, 600px wide, for the README
  icon-*.png        the mark trimmed out of its margins and centred on a rounded
                    tile of the same cream, so it fills the icon

Re-run it after replacing the artwork: python assets/make_icon.py [artwork]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "logo-source.png"
ICON_SIZES = (512, 256, 128, 64, 32)
FILL = 0.86          # of the tile's height the mark takes up
RADIUS_FRAC = 0.22   # rounded-tile corner radius


def ground(im: Image.Image) -> tuple[int, int, int]:
    """The artwork's own background colour, read from a corner pixel."""
    return im.convert("RGB").getpixel((4, 4))


def mark_box(im: Image.Image, bg: tuple[int, int, int], tol: int = 18):
    """Bounding box of everything that is not the background.

    Tolerance rather than an exact match: the export is lossy, so the cream is
    not one value, and an exact test would treat compression noise as artwork
    and return the whole canvas.
    """
    a = np.asarray(im.convert("RGB")).astype(int)
    mask = np.abs(a - np.array(bg)).max(axis=2) > tol
    ys, xs = mask.nonzero()
    if not len(xs):
        return (0, 0, im.width, im.height)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def tile(size: int, bg: tuple[int, int, int]) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=int(size * RADIUS_FRAC),
        fill=bg + (255,))
    return canvas


def build_icon(mark: Image.Image, size: int, bg) -> Image.Image:
    canvas = tile(size, bg)
    m = mark.copy()
    m.thumbnail((int(size * FILL), int(size * FILL)), Image.LANCZOS)
    canvas.paste(m, ((size - m.width) // 2, (size - m.height) // 2))
    return canvas


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"artwork not found: {SRC}")

    art = Image.open(SRC).convert("RGB")
    bg = ground(art)
    box = mark_box(art, bg)
    mark = art.crop(box)

    art.copy().resize((600, round(600 * art.height / art.width)),
                      Image.LANCZOS).save(HERE / "logo-600.png")

    for s in ICON_SIZES:
        build_icon(mark, s, bg).save(HERE / f"icon-{s}.png")
    build_icon(mark, 256, bg).save(HERE / "icon.png")

    print(f"source {SRC.name} {art.size}, ground {bg}, mark {mark.size}")
    print("wrote  logo-600.png (README header)")
    print("wrote ", ", ".join(f"icon-{s}.png" for s in ICON_SIZES), "+ icon.png")


if __name__ == "__main__":
    main()

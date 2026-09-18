"""Build every image the project needs from the one mascot artwork.

The mascot is a full-body illustration with a readable newspaper in it. That
works at 600px in a README and is unreadable at 32px in the Extensions list, so
this script cuts two different things from the same source:

  mascot-600.png    the whole figure, background knocked out, for the README
  icon-*.png        head and shoulders only, on a solid rounded tile, for the
                    app icon - because at 32px a full body is four grey pixels
                    and a hat, while a face still reads as a face

The full-resolution figure and the head and face crops are steps on the way to
those, not deliverables, so they stay in memory. Everything this writes is
something the project actually references; nothing here is an orphan.

Everything lives in this folder, source artwork included, and every output is
written beside the script rather than into the current working directory - so it
behaves the same whether it is run from here or from the project root.

Re-run it after editing the artwork: python assets/make_icon.py [artwork]
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "MCP LOGO MASCOT.png"
TILE = (36, 32, 58)        # deep aubergine, pulled from the mascot's plumage
ICON_SIZES = (512, 256, 128, 64, 32)


def knockout_white(im: Image.Image, cutoff: int = 236) -> Image.Image:
    """Remove the white BACKGROUND only - not white inside the artwork.

    The first version tested every pixel against a colour threshold, which ate
    anything pale wherever it happened to be: the silver P on the hat turned
    transparent and the tile showed through it, so the hat read "MC" with a hole.
    The owl's white facial feathers and the newsprint were at risk of the same.

    Background is not a colour, it is the region connected to the edge of the
    frame. So: build a near-white mask, label its connected components, and drop
    only the components that touch the border. A white shape sealed inside the
    drawing is never touched, however bright it is.
    """
    import numpy as np
    from scipy import ndimage

    im = im.convert("RGBA")
    a = np.asarray(im).astype(np.int16)
    rgb = a[..., :3]
    near_white = (rgb.min(axis=2) >= cutoff) & (np.ptp(rgb, axis=2) <= 12)

    labels, n = ndimage.label(near_white)
    if n:
        border = np.concatenate([labels[0, :], labels[-1, :],
                                 labels[:, 0], labels[:, -1]])
        outside = np.isin(labels, np.setdiff1d(np.unique(border), [0]))
    else:
        outside = np.zeros_like(near_white)

    alpha = a[..., 3].astype(np.float32)
    alpha[outside] = 0.0

    # Feather one ring inward so the cut edge is not a hard staircase, which
    # shows as a white fringe the moment the logo sits on a dark README.
    edge = ndimage.binary_dilation(outside, iterations=1) & ~outside
    alpha[edge] *= 0.5

    out = a.astype(np.uint8)
    out[..., 3] = np.clip(alpha, 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def trim(im: Image.Image, pad: int = 8) -> Image.Image:
    box = im.getbbox()
    if not box:
        return im
    l, t, r, b = box
    return im.crop((max(0, l - pad), max(0, t - pad),
                    min(im.width, r + pad), min(im.height, b + pad)))


def rounded_tile(size: int, radius_frac: float = 0.22) -> Image.Image:
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    d.rounded_rectangle((0, 0, size - 1, size - 1),
                        radius=int(size * radius_frac), fill=TILE + (255,))
    return tile


def build_icon(head: Image.Image, size: int,
               fill: float = 0.82) -> Image.Image:
    """Head on a tile, sized so the face fills the square without crowding it."""
    canvas = rounded_tile(size)
    inner = int(size * fill)
    h = head.copy()
    h.thumbnail((inner, inner), Image.LANCZOS)
    # Sit it slightly high: the hat reads better with air under the chin than
    # over the brim.
    x = (size - h.width) // 2
    y = int((size - h.height) * 0.46)
    canvas.alpha_composite(h, (x, y))
    return canvas


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"artwork not found: {SRC}")

    art = knockout_white(Image.open(SRC))
    full = trim(art)
    full.copy().resize(
        (600, int(600 * full.height / full.width)), Image.LANCZOS
    ).save(HERE / "mascot-600.png")

    # Head and hat only. The first cut reached far enough left to catch the
    # newspaper, and at 32px a slice of masthead beside the face is just noise
    # competing with the one shape that has to survive.
    w, h = full.size
    head = full.crop((int(w * 0.345), int(h * 0.015), int(w * 0.95), int(h * 0.385)))
    head = trim(head, pad=2)

    # Below about 96px the hat stops being a hat and becomes a dark smudge
    # against a dark tile, so the small icons drop it and let the eyes and
    # glasses - the two shapes that still read at that size - fill the frame.
    face = trim(head.crop((0, int(head.height * 0.30), head.width, head.height)),
                pad=2)
    # Square it, centred on the eyes, or the wide face letterboxes inside the
    # square tile and wastes half the pixels the icon has to work with.
    fw, fh = face.size
    if fw > fh:
        left = (fw - fh) // 2
        face = face.crop((left, 0, left + fh, fh))
    elif fh > fw:
        face = face.crop((0, 0, fw, fw))

    for s in ICON_SIZES:
        small = s < 96
        build_icon(face if small else head, s,
                   fill=0.94 if small else 0.82).save(HERE / f"icon-{s}.png")
    build_icon(head, 256).save(HERE / "icon.png")

    print(f"source {SRC.name} {art.size} -> figure {full.size}, head {head.size}")
    print("wrote  mascot-600.png (README header)")
    print("wrote ", ", ".join(f"icon-{s}.png" for s in ICON_SIZES), "+ icon.png")


if __name__ == "__main__":
    main()

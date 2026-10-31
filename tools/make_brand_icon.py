#!/usr/bin/env python3
"""Draw the brand icon HACS and the Home Assistant brands repo ask for.

Original artwork, deliberately: the panel plate and every mark on it belong to
somebody else (see NOTICE), so the one image this repo can actually license is
one drawn from scratch. A seven-bar level meter is the honest subject - the
live meter is what the card is for.

Palette is the card's own: the bar gradient sampled off the artwork, and the
lime green the panel uses to mark the live selection, on the peak bar.

Transparent background, because the icon is shown on both light and dark
Home Assistant themes; the greys are kept in the top half of the plate's
gradient so they carry on either.

Writes custom_components/minidsp_tide16/brand/icon.png (256) and icon@2x.png (512),
which are the sizes the brands repo requires.

Run:  python3 tools/make_brand_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "custom_components" / "minidsp_tide16" / "brand"

# Drawn big and downsampled - the bar edges and the rounded caps need the
# supersampling to come out clean at 256.
MASTER = 2048

# Heights as a fraction of the drawable box, left to right. Shaped like a real
# meter mid-programme rather than a tidy ramp: a peak left of centre, the
# surrounds lower, the last pair down where unassigned outputs sit.
BARS = [0.52, 0.74, 1.00, 0.86, 0.62, 0.40, 0.30]

GREY_TOP = (232, 232, 232)
GREY_BOTTOM = (106, 107, 107)
GREEN_TOP = (86, 224, 86)
GREEN_BOTTOM = (31, 125, 31)
PEAK = 2  # index of the bar that gets the accent


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def draw(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    margin = size * 0.14
    box = size - 2 * margin
    # Bars sit on a shared baseline and are windows onto one gradient that
    # spans the whole box - the same rule the card's meter follows, so a short
    # bar starts dimmer than a tall one instead of repeating the full ramp.
    pitch = box / len(BARS)
    width = pitch * 0.62
    radius = width * 0.28
    baseline = margin + box

    for i, height in enumerate(BARS):
        top_c, bottom_c = (GREEN_TOP, GREEN_BOTTOM) if i == PEAK else (GREY_TOP, GREY_BOTTOM)
        x0 = margin + i * pitch + (pitch - width) / 2
        top = baseline - box * height
        bar = Image.new("RGBA", (round(width), round(baseline - top)), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bar)
        for y in range(bar.height):
            # t is the row's place in the FULL box, not in this bar.
            t = (top - margin + y) / box
            bd.line([(0, y), (bar.width, y)], fill=lerp(top_c, bottom_c, t) + (255,))

        mask = Image.new("L", bar.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, bar.width - 1, bar.height - 1], radius=radius, fill=255
        )
        img.paste(bar, (round(x0), round(top)), mask)

    del d
    return img


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    master = draw(MASTER)
    for name, px in (("icon.png", 256), ("icon@2x.png", 512)):
        master.resize((px, px), Image.LANCZOS).save(OUT / name)
        print(f"wrote {(OUT / name).relative_to(ROOT)} ({px}x{px})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Render the README banner at docs/banner.png.

The banner is drawn in the panel's own three inks (white paper, black, red)
with the panel's own font, and the device on the right is the real renderer's
output for a placeholder kid, scaled up pixel-for-pixel, so the banner can't
drift from what the e-paper shows. Deterministic: no clock reads, no random.

    python3 scripts/make_banner.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from beanclock.age import AgeBreakdown
from beanclock.render import _font, compose_preview, render

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "docs" / "banner.png"

WIDTH, HEIGHT = 1600, 400
PAPER = (255, 255, 255)
INK = (0, 0, 0)
RED = (208, 32, 32)
SCALE = 3  # the panel's 250×122 becomes 750×366, pixel-for-pixel

BORN = datetime(2023, 3, 14, 9, 0, tzinfo=timezone(timedelta(hours=-7)))
AGE = AgeBreakdown(years=3, months=3, days=15, hours=1, total_days=1203, total_hours=28873)


def heart(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, fill: tuple[int, int, int]) -> None:
    """A heart from two discs and a triangle, like the panel's corner beads."""
    draw.ellipse((cx - r, cy - r, cx, cy), fill=fill)
    draw.ellipse((cx, cy - r, cx + r, cy), fill=fill)
    draw.polygon([(cx - r, cy - r // 3), (cx + r, cy - r // 3), (cx, cy + r)], fill=fill)


def main() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(image)

    # The panel, rendered for real and scaled without smoothing so the pixels stay crisp.
    black, red = render("Bean", AGE, BORN, accent="heart")
    panel = compose_preview(black, red).convert("RGB")
    panel = panel.resize((panel.width * SCALE, panel.height * SCALE), Image.Resampling.NEAREST)
    px = WIDTH - panel.width - 60
    py = (HEIGHT - panel.height) // 2
    bezel = 10
    draw.rounded_rectangle(
        (px - bezel, py - bezel, px + panel.width + bezel, py + panel.height + bezel),
        radius=14, fill=INK,
    )
    image.paste(panel, (px, py))

    # Wordmark, tagline and a row of beads, in the panel's rounded face.
    x = 70
    draw.text((x, 92), "BeanClock", font=_font(118, "Bold"), fill=INK)
    draw.text((x + 4, 232), "how old the kiddo is, to the hour", font=_font(40, "Medium"), fill=INK)
    draw.text(
        (x + 4, 286), "Pi Zero 2 W  ·  2.13-inch three-colour e-paper  ·  hourly",
        font=_font(26, "Regular"), fill=INK,
    )
    for i in range(7):
        heart(draw, x + 14 + i * 34, 52, 9, RED if i % 2 == 0 else INK)

    # Snap to the three inks, as the panel would.
    palette = Image.new("P", (1, 1))
    palette.putpalette(list(PAPER) + list(INK) + list(RED) + [0, 0, 0] * 253)
    image = image.quantize(palette=palette, dither=Image.Dither.FLOYDSTEINBERG).convert("RGB")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT_PATH, optimize=True)
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)} ({WIDTH}×{HEIGHT})")


if __name__ == "__main__":
    main()

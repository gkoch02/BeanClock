from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from kidage.age import AgeBreakdown, pluralize

WIDTH = 250
HEIGHT = 122

FONT_PATH = Path(__file__).resolve().parent.parent / "fonts" / "Fredoka.ttf"


def _font(size: int, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONT_PATH), size=size)
    f.set_variation_by_name(weight)
    return f


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
) -> None:
    w = _text_width(draw, text, font)
    draw.text(((WIDTH - w) // 2, y), text, font=font, fill=0)


def _hero_line(age: AgeBreakdown) -> str:
    if age.years == 0:
        return pluralize(age.months, "month") if age.months else "newborn"
    return f"{pluralize(age.years, 'year')}  {pluralize(age.months, 'month')}"


def _sub_line(age: AgeBreakdown) -> str:
    return f"{pluralize(age.days, 'day')}  ·  {pluralize(age.hours, 'hour')}"


def _draw_heart(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 9) -> None:
    r = size // 2
    draw.ellipse((cx - size + 1, cy - r, cx, cy + r - 1), fill=0)
    draw.ellipse((cx, cy - r, cx + size - 1, cy + r - 1), fill=0)
    draw.polygon(
        [(cx - size + 1, cy), (cx + size - 1, cy), (cx, cy + size)],
        fill=0,
    )


def _draw_star(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 8) -> None:
    import math

    points = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        r = size if i % 2 == 0 else size * 0.45
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=0)


def _draw_balloon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 10) -> None:
    draw.ellipse((cx - size, cy - size, cx + size, cy + size - 2), fill=0)
    draw.polygon(
        [(cx - 2, cy + size - 3), (cx + 2, cy + size - 3), (cx, cy + size + 1)],
        fill=0,
    )
    draw.line((cx, cy + size + 1, cx, cy + size + 5), fill=0, width=1)


_ACCENTS = {"heart": _draw_heart, "star": _draw_star, "balloon": _draw_balloon}


# Frame geometry. The outer black line sits at the panel edge; the red beads
# trim the inside of that line. The text region must clear FRAME_PAD on every
# side so it doesn't collide with the trim.
FRAME_OUTER = 1            # 1px inset for the rounded black line
FRAME_BEAD_INSET = 5       # bead centers sit FRAME_BEAD_INSET px from the edge
FRAME_BEAD_SPACING = 10
FRAME_PAD = 9              # min y-distance from text to the panel edge


def _draw_bead(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    draw.ellipse((cx - 1, cy - 1, cx + 1, cy + 1), fill=0)


def _draw_corner_dot(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=0)


def _draw_frame(
    bd: ImageDraw.ImageDraw,
    rd: ImageDraw.ImageDraw,
    accent: str,
    accent_fn,
) -> None:
    # Outer rounded black hairline.
    bd.rounded_rectangle(
        (FRAME_OUTER, FRAME_OUTER, WIDTH - 1 - FRAME_OUTER, HEIGHT - 1 - FRAME_OUTER),
        radius=8,
        outline=0,
        width=1,
    )

    # Red beads, evenly spaced along each inside edge, skipping the corners
    # so they don't clash with the rounded outer line or the corner accents.
    inset = FRAME_BEAD_INSET
    left, right = inset, WIDTH - 1 - inset
    top, bottom = inset, HEIGHT - 1 - inset
    corner_skip = 14

    for x in range(left + corner_skip, right - corner_skip + 1, FRAME_BEAD_SPACING):
        _draw_bead(rd, x, top)
        _draw_bead(rd, x, bottom)
    for y in range(top + corner_skip, bottom - corner_skip + 1, FRAME_BEAD_SPACING):
        _draw_bead(rd, left, y)
        _draw_bead(rd, right, y)

    corners = ((9, 9), (WIDTH - 10, 9), (9, HEIGHT - 10), (WIDTH - 10, HEIGHT - 10))
    for cx, cy in corners:
        if accent == "heart":
            _draw_corner_dot(rd, cx, cy)
        else:
            accent_fn(rd, cx, cy, size=4)


def _format_birthday(born_at: datetime) -> str:
    return born_at.strftime("%b ") + str(born_at.day) + born_at.strftime(", %Y")


def render(
    name: str,
    age: AgeBreakdown,
    born_at: datetime,
    accent: str = "heart",
    flip: bool = False,
    age_format: str = "extended",
) -> tuple[Image.Image, Image.Image]:
    black = Image.new("1", (WIDTH, HEIGHT), 1)
    red = Image.new("1", (WIDTH, HEIGHT), 1)
    bd = ImageDraw.Draw(black)
    rd = ImageDraw.Draw(red)

    accent_fn = _ACCENTS.get(accent, _draw_heart)

    _draw_frame(bd, rd, accent, accent_fn)

    header_font = _font(20, "Medium")
    header = f"{name} is"
    hw = _text_width(rd, header, header_font)
    hx = (WIDTH - hw) // 2
    hy = FRAME_PAD
    rd.text((hx, hy), header, font=header_font, fill=0)

    accent_y = hy + 10
    accent_fn(rd, hx - 14, accent_y)
    accent_fn(rd, hx + hw + 14, accent_y)

    if age_format == "days":
        hero = pluralize(age.total_days, "day")
        hero_y = 47
        sub = None
    elif age_format == "hours":
        hero = pluralize(age.total_hours, "hour")
        hero_y = 47
        sub = None
    else:
        hero = _hero_line(age)
        hero_y = 33
        sub = _sub_line(age)

    hero_size = 28
    hero_font = _font(hero_size, "Bold")
    while _text_width(bd, hero, hero_font) > WIDTH - 28 and hero_size > 16:
        hero_size -= 2
        hero_font = _font(hero_size, "Bold")
    _draw_centered(bd, hero_y, hero, hero_font)

    if sub is not None:
        sub_font = _font(17, "Medium")
        _draw_centered(bd, 68, sub, sub_font)

    footer_font = _font(13, "Regular")
    footer = f"since {_format_birthday(born_at)}"
    fw = _text_width(rd, footer, footer_font)
    fx = (WIDTH - fw) // 2
    fy = HEIGHT - FRAME_PAD - 13
    rd.text((fx, fy), footer, font=footer_font, fill=0)
    if accent != "heart":
        accent_fn(rd, fx - 12, fy + 8, size=7)

    if flip:
        black = black.rotate(180)
        red = red.rotate(180)

    return black, red


def compose_preview(black: Image.Image, red: Image.Image) -> Image.Image:
    out = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))
    px = out.load()
    bp = black.load()
    rp = red.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if bp[x, y] == 0:
                px[x, y] = (0, 0, 0)
            elif rp[x, y] == 0:
                px[x, y] = (220, 30, 30)
    return out

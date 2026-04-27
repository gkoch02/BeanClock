from datetime import datetime, timezone, timedelta

from kidage.age import AgeBreakdown
from kidage.render import FRAME_PAD, HEIGHT, WIDTH, compose_preview, render


PT = timezone(timedelta(hours=-7))
BORN = datetime(2022, 9, 12, 3, 47, tzinfo=PT)


def _has_ink(img):
    return b"\x00" in img.tobytes()


def _ink_x_extent(img, y_range, x_range=None):
    """Return (min_x, max_x) of inked pixels in the given y/x range, or None."""
    px = img.load()
    x_range = x_range or range(WIDTH)
    xs = [x for y in y_range for x in x_range if px[x, y] == 0]
    return (min(xs), max(xs)) if xs else None


def test_render_returns_two_planes_at_panel_size():
    age = AgeBreakdown(3, 7, 15, 4)
    black, red = render("Lily", age, BORN)
    assert black.size == (WIDTH, HEIGHT)
    assert red.size == (WIDTH, HEIGHT)
    assert black.mode == "1"
    assert red.mode == "1"
    assert _has_ink(black)
    assert _has_ink(red)


def test_render_handles_newborn():
    age = AgeBreakdown(0, 0, 0, 1)
    black, red = render("Lily", age, BORN)
    assert _has_ink(black)


def test_render_flip_rotates_both_planes():
    age = AgeBreakdown(3, 7, 15, 4)
    upright = render("Lily", age, BORN, flip=False)
    flipped = render("Lily", age, BORN, flip=True)
    assert upright[0].tobytes() != flipped[0].tobytes()
    assert upright[1].tobytes() != flipped[1].tobytes()


def test_compose_preview_is_rgb_panel_size():
    age = AgeBreakdown(3, 7, 15, 4)
    black, red = render("Lily", age, BORN)
    p = compose_preview(black, red)
    assert p.size == (WIDTH, HEIGHT)
    assert p.mode == "RGB"


def test_render_accepts_known_accents():
    age = AgeBreakdown(2, 0, 0, 0)
    for accent in ("heart", "star", "balloon"):
        b, r = render("Lily", age, BORN, accent=accent)
        assert _has_ink(r)


def test_accents_produce_distinct_red_planes():
    """Each accent must actually paint differently; otherwise an accent-fn
    regression (e.g. _ACCENTS.get always returning the default) would slip
    past the existing "ink exists" check."""
    age = AgeBreakdown(2, 0, 0, 0)
    planes = {
        a: render("Lily", age, BORN, accent=a)[1].tobytes()
        for a in ("heart", "star", "balloon")
    }
    assert planes["heart"] != planes["star"]
    assert planes["star"] != planes["balloon"]
    assert planes["heart"] != planes["balloon"]


def test_text_clears_frame_pad_margin():
    """Text must not bleed into the FRAME_PAD margin rows.

    CLAUDE.md: 'Resizing text or moving the frame in isolation will produce
    clipping; adjust both.' We sample the central x-band (skipping the
    rounded-corner arcs of the outer black hairline) and assert no black
    text ink in the top and bottom keep-out strips.
    """
    age = AgeBreakdown(3, 7, 15, 4)
    black, _ = render("Lily", age, BORN)
    bp = black.load()

    for y in range(2, FRAME_PAD):
        for x in range(20, WIDTH - 20):
            assert bp[x, y] == 1, f"black ink in top margin at ({x}, {y})"
    for y in range(HEIGHT - FRAME_PAD, HEIGHT - 2):
        for x in range(20, WIDTH - 20):
            assert bp[x, y] == 1, f"black ink in bottom margin at ({x}, {y})"


def test_hero_auto_shrinks_to_stay_within_width_budget():
    """The hero shrink loop (render.py:168) caps text width at WIDTH-28.
    A long hero like '99 years  11 months' should still center within the
    budgeted band (left edge >= 14, right edge <= WIDTH-14). We restrict
    the x search to skip the frame outline at x=1 and x=WIDTH-2."""
    long_age = AgeBreakdown(99, 11, 30, 23)
    black, _ = render("Lily", long_age, BORN)
    inner = range(10, WIDTH - 10)
    extent = _ink_x_extent(black, range(33, 62), inner)
    assert extent is not None, "expected hero ink"
    left, right = extent
    assert left >= 14, f"hero overflows left budget: {left}"
    assert right <= WIDTH - 14, f"hero overflows right budget: {right}"


def test_long_hero_would_overflow_at_default_size():
    """Sanity check that the budget test above actually exercises the shrink
    path: '99 years  11 months' at 28pt Bold must exceed WIDTH-28. If the
    font ever changes to narrower glyphs and this stops being true, the
    budget test no longer proves shrink works — pick a longer input."""
    from PIL import Image, ImageDraw

    from kidage.render import _font, _text_width

    bd = ImageDraw.Draw(Image.new("1", (WIDTH, HEIGHT), 1))
    f28 = _font(28, "Bold")
    assert _text_width(bd, "99 years  11 months", f28) > WIDTH - 28

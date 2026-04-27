from datetime import datetime, timezone, timedelta

from kidage.age import AgeBreakdown
from kidage.render import HEIGHT, WIDTH, compose_preview, render


PT = timezone(timedelta(hours=-7))
BORN = datetime(2022, 9, 12, 3, 47, tzinfo=PT)


def _has_ink(img):
    return b"\x00" in img.tobytes()


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

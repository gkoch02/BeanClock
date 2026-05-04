from datetime import datetime, timedelta, timezone

from kidage.age import AgeBreakdown
from kidage.render import FRAME_PAD, HEIGHT, WIDTH, compose_preview, render

PT = timezone(timedelta(hours=-7))
BORN = datetime(2022, 9, 12, 3, 47, tzinfo=PT)

# Canonical age fixtures. Totals are realistic for the calendar values so that
# format="days"/"hours" rendering is exercised with plausible inputs.
AGE = AgeBreakdown(3, 7, 15, 4, total_days=1324, total_hours=31780)
NEWBORN = AgeBreakdown(0, 0, 0, 1, total_days=0, total_hours=1)
TWO_YEARS = AgeBreakdown(2, 0, 0, 0, total_days=730, total_hours=17520)
LONG_AGE = AgeBreakdown(99, 11, 30, 23, total_days=36524, total_hours=876575)


def _has_ink(img):
    # Any byte < 0xff means at least one of its 8 packed pixels is black.
    # Checking for b"\x00" directly would miss thin or cutout glyphs that
    # never leave 8 byte-aligned contiguous black pixels (e.g. moon, flower).
    return any(byte != 0xFF for byte in img.tobytes())


def _ink_x_extent(img, y_range, x_range=None):
    """Return (min_x, max_x) of inked pixels in the given y/x range, or None."""
    px = img.load()
    x_range = x_range or range(WIDTH)
    xs = [x for y in y_range for x in x_range if px[x, y] == 0]
    return (min(xs), max(xs)) if xs else None


def test_render_returns_two_planes_at_panel_size():
    black, red = render("Lily", AGE, BORN)
    assert black.size == (WIDTH, HEIGHT)
    assert red.size == (WIDTH, HEIGHT)
    assert black.mode == "1"
    assert red.mode == "1"
    assert _has_ink(black)
    assert _has_ink(red)


def test_render_handles_newborn():
    black, red = render("Lily", NEWBORN, BORN)
    assert _has_ink(black)


def test_render_flip_rotates_both_planes():
    upright = render("Lily", AGE, BORN, flip=False)
    flipped = render("Lily", AGE, BORN, flip=True)
    assert upright[0].tobytes() != flipped[0].tobytes()
    assert upright[1].tobytes() != flipped[1].tobytes()


def test_render_after_hours_inverts_black_only():
    """after_hours flips black/white but leaves red untouched, so the
    panel reads white-on-black with red beads still in place."""
    normal = render("Lily", AGE, BORN)
    inverted = render("Lily", AGE, BORN, after_hours=True)
    assert normal[0].tobytes() != inverted[0].tobytes()
    assert normal[1].tobytes() == inverted[1].tobytes()


def test_render_after_hours_makes_background_inked():
    """After inversion, what used to be the white panel background should
    now be inked on the black plane. Sample a margin pixel that's outside
    the frame and well clear of any glyphs."""
    normal_black, _ = render("Lily", AGE, BORN)
    inv_black, _ = render("Lily", AGE, BORN, after_hours=True)
    np = normal_black.load()
    ip = inv_black.load()
    # (0, 0) is the very top-left corner — outside the rounded frame, so
    # it's blank white in the normal render and should be ink after
    # inversion.
    assert np[0, 0] == 1
    assert ip[0, 0] == 0


def test_render_after_hours_punches_black_out_under_red_ink():
    """The Waveshare driver ORs the two planes onto the panel, so a
    naive 'invert all of black' would mask out red. Verify that wherever
    the red plane has ink, the inverted black plane is *not* inked, so
    red still shows through against the new black background."""
    _, red = render("Lily", AGE, BORN)
    inv_black, _ = render("Lily", AGE, BORN, after_hours=True)
    rp = red.load()
    bp = inv_black.load()
    red_pixels = [
        (x, y) for y in range(HEIGHT) for x in range(WIDTH) if rp[x, y] == 0
    ]
    assert red_pixels, "expected the normal render to produce some red ink"
    for x, y in red_pixels:
        assert bp[x, y] == 1, (
            f"black plane is inked at red pixel ({x}, {y}) — "
            "would mask red on the panel"
        )


def test_render_after_hours_combines_with_flip():
    """flip and after_hours are independent and must compose. Inverted-
    then-flipped should differ from just-inverted, just-flipped, and
    plain renders."""
    plain = render("Lily", AGE, BORN)[0].tobytes()
    flipped = render("Lily", AGE, BORN, flip=True)[0].tobytes()
    inverted = render("Lily", AGE, BORN, after_hours=True)[0].tobytes()
    both = render("Lily", AGE, BORN, flip=True, after_hours=True)[0].tobytes()
    assert len({plain, flipped, inverted, both}) == 4


def test_compose_preview_is_rgb_panel_size():
    black, red = render("Lily", AGE, BORN)
    p = compose_preview(black, red)
    assert p.size == (WIDTH, HEIGHT)
    assert p.mode == "RGB"


ACCENTS = ("heart", "star", "balloon", "moon", "sun", "flower")


def test_render_accepts_known_accents():
    for accent in ACCENTS:
        b, r = render("Lily", TWO_YEARS, BORN, accent=accent)
        assert _has_ink(r)


def test_accents_produce_distinct_red_planes():
    """Each accent must actually paint differently; otherwise an accent-fn
    regression (e.g. _ACCENTS.get always returning the default) would slip
    past the existing "ink exists" check."""
    planes = [
        render("Lily", TWO_YEARS, BORN, accent=a)[1].tobytes() for a in ACCENTS
    ]
    for i, a in enumerate(planes):
        for b in planes[i + 1 :]:
            assert a != b


def test_text_clears_frame_pad_margin():
    """Text must not bleed into the FRAME_PAD margin rows.

    CLAUDE.md: 'Resizing text or moving the frame in isolation will produce
    clipping; adjust both.' We sample the central x-band (skipping the
    rounded-corner arcs of the outer black hairline) and assert no black
    text ink in the top and bottom keep-out strips.
    """
    black, _ = render("Lily", AGE, BORN)
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
    black, _ = render("Lily", LONG_AGE, BORN)
    inner = range(10, WIDTH - 10)
    extent = _ink_x_extent(black, range(33, 62), inner)
    assert extent is not None, "expected hero ink"
    left, right = extent
    assert left >= 14, f"hero overflows left budget: {left}"
    assert right <= WIDTH - 14, f"hero overflows right budget: {right}"


def test_format_modes_produce_distinct_planes():
    """Each age_format must visibly change the black plane; otherwise a
    regression that ignored the new field would slip past the per-format
    smoke checks below."""
    planes = {
        fmt: render("Lily", AGE, BORN, age_format=fmt)[0].tobytes()
        for fmt in ("extended", "days", "hours", "full")
    }
    assert planes["extended"] != planes["days"]
    assert planes["days"] != planes["hours"]
    assert planes["extended"] != planes["hours"]
    assert planes["extended"] != planes["full"]
    assert planes["days"] != planes["full"]


def test_format_full_adds_ink_in_bottom_corners():
    """`full` augments the extended layout with compact total readouts in
    the bottom-left and bottom-right of the black plane. The two corners
    must gain ink relative to plain extended; otherwise the totals aren't
    actually being painted."""
    extended_black, _ = render("Lily", AGE, BORN, age_format="extended")
    full_black, _ = render("Lily", AGE, BORN, age_format="full")
    footer_band = range(HEIGHT - FRAME_PAD - 13, HEIGHT - FRAME_PAD)
    left = range(10, 60)
    right = range(WIDTH - 60, WIDTH - 10)
    ext_left = _ink_x_extent(extended_black, footer_band, left)
    full_left = _ink_x_extent(full_black, footer_band, left)
    ext_right = _ink_x_extent(extended_black, footer_band, right)
    full_right = _ink_x_extent(full_black, footer_band, right)
    assert ext_left is None and full_left is not None, (
        "full mode should add black ink in the bottom-left corner"
    )
    assert ext_right is None and full_right is not None, (
        "full mode should add black ink in the bottom-right corner"
    )


def test_format_full_uses_total_fields_not_calendar():
    """The corner totals must reflect age.total_days / age.total_hours.
    Two ages with identical calendar (years/months/days/hours) but
    different totals should diverge in the bottom band of the black
    plane (where the hero/sub above is identical)."""
    big = AgeBreakdown(3, 7, 15, 4, total_days=1324, total_hours=31780)
    small = AgeBreakdown(3, 7, 15, 4, total_days=42, total_hours=999)
    big_black, _ = render("Lily", big, BORN, age_format="full")
    small_black, _ = render("Lily", small, BORN, age_format="full")
    assert big_black.tobytes() != small_black.tobytes()


def test_format_full_preserves_extended_hero_and_sub():
    """`full` differs from `extended` only in the footer row. The hero
    band (y=33..62) and sub band (y=68..86) must be byte-identical so
    layout regressions in the upper region get caught here rather than
    drowning in the bottom-corner diff."""
    extended_black, _ = render("Lily", AGE, BORN, age_format="extended")
    full_black, _ = render("Lily", AGE, BORN, age_format="full")
    ep = extended_black.load()
    fp = full_black.load()
    for y in list(range(33, 62)) + list(range(68, 86)):
        for x in range(WIDTH):
            assert ep[x, y] == fp[x, y], (
                f"upper layout diverges at ({x}, {y})"
            )


def test_format_days_short_circuits_zero_to_newborn():
    """In days mode, total_days=0 must render "newborn" rather than
    "0 days". We pin this by rendering the same AgeBreakdown in days
    mode and in hours mode (with the total_hours also 0): both fall
    into the newborn branch, so their hero text — and thus the black
    plane below the header — should be identical."""
    fresh = AgeBreakdown(0, 0, 0, 0, total_days=0, total_hours=0)
    days_black, _ = render("Lily", fresh, BORN, age_format="days")
    hours_black, _ = render("Lily", fresh, BORN, age_format="hours")
    assert days_black.tobytes() == hours_black.tobytes()


def test_format_days_uses_total_days_not_calendar_days():
    """Hero text in days mode must reflect total_days (e.g. 1324) rather
    than the calendar `days` field (15). If render() reads age.days by
    mistake, a small total_days input renders the same as a small
    calendar-days input — pin the distinction."""
    big = AgeBreakdown(0, 0, 15, 0, total_days=1324, total_hours=31780)
    small = AgeBreakdown(0, 0, 15, 0, total_days=15, total_hours=360)
    big_black, _ = render("Lily", big, BORN, age_format="days")
    small_black, _ = render("Lily", small, BORN, age_format="days")
    assert big_black.tobytes() != small_black.tobytes()


def test_special_hero_replaces_normal_hero():
    """In special-day mode the hero text is the override string, and the
    standard "Y years M months" phrasing is demoted to the sub line — so
    the black plane must differ from the non-special render."""
    plain = render("Lily", AGE, BORN)[0].tobytes()
    special = render("Lily", AGE, BORN, special="Happy 4th Birthday!")[0].tobytes()
    assert plain != special


def test_special_overrides_days_format():
    """Special days take over regardless of age_format. Pin this so a future
    refactor doesn't accidentally restore the days/hours hero on a milestone."""
    days = render("Lily", AGE, BORN, age_format="days")[0].tobytes()
    special = render(
        "Lily", AGE, BORN, age_format="days", special="1000 days!"
    )[0].tobytes()
    assert days != special


def test_special_long_label_respects_width_budget():
    """'Happy 99th Birthday!' must shrink rather than overflow the frame —
    the same shrink loop the standard hero relies on."""
    black, _ = render("Lily", LONG_AGE, BORN, special="Happy 99th Birthday!")
    inner = range(10, WIDTH - 10)
    extent = _ink_x_extent(black, range(33, 62), inner)
    assert extent is not None
    left, right = extent
    assert left >= 14
    assert right <= WIDTH - 14


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

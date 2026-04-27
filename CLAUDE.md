# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Raspberry Pi Zero W 2 appliance that renders a kid's age (years / months /
days / hours) onto a Waveshare 2.13" b/w/r e-paper (V4, 250×122). A `systemd`
timer fires `python -m kidage` every hour from 07:00–21:00; each run is a
oneshot that loads the TOML config, computes the age, paints two PIL bitmaps
(one per ink plane), pushes them to the panel, puts the panel to sleep, and
exits. There is no daemon.

## Common commands

```bash
# Dev environment (laptop, no panel needed)
pip install -e '.[dev]'

# All tests — entire suite is hardware-free
pytest

# One test file / one test
pytest tests/test_render.py
pytest tests/test_age.py::test_leap_day_birth -v

# Render a PNG preview of the current layout without touching hardware
python -m kidage --config config.example.toml --preview /tmp/p.png
# Pin the wall clock for deterministic previews (e.g. while tweaking layout)
python -m kidage --config config.example.toml --preview /tmp/p.png \
    --now 2026-04-27T07:47:00-07:00

# On the Pi: install the appliance (idempotent)
sudo bash scripts/install.sh
# Force a refresh now (also exercises the real driver path)
sudo systemctl start kidage.service
journalctl -u kidage.service -f
```

## Architecture

`kidage/__main__.py` is the only entrypoint. It loads `kidage.config` →
calls `kidage.age.compute` → calls `kidage.render.render` → either writes a
PNG (`--preview`) or calls `kidage.display.show`. The split exists so the
render path is hardware-free and exercised by tests, while `display.py`
isolates the `RPi.GPIO` / `spidev` blast radius.

**Image planes (the easy thing to get wrong).** `render()` returns two PIL
images, both mode `"1"`, both at the panel's native 250×122. In each plane
the pixel value `0` means "ink here" and `1` means "leave alone" — *the same
convention applies to both the black and red planes*. To draw red, paint
black (`fill=0`) on the red plane. The vendored Waveshare driver ORs the
two planes onto the panel.

**Lazy hardware import.** `kidage.display.show` does `from
vendor.waveshare_epd import epd2in13b_V4` *inside* the function so importing
`kidage.render` (and running the test suite) on a non-Pi machine doesn't
require `RPi.GPIO`/`spidev`. Don't move that import to module scope.

**Once-a-day clear.** `display.show` consults `/var/lib/kidage/last-clear`
and only calls `epd.Clear()` on the first refresh of a given local date.
The other ~14 hourly refreshes go straight to `epd.display()`, which avoids
the tri-color panel's full inversion flicker. To force a clear on the next
run, delete that file. The state directory is overridable via
`KIDAGE_STATE_DIR` (the `systemd` unit sets it via `StateDirectory=kidage`).

**Variable font.** `fonts/Fredoka.ttf` is a single variable TTF with weight
and width axes. `render._font(size, weight)` calls
`set_variation_by_name(weight)` (`Light` / `Regular` / `Medium` / `SemiBold`
/ `Bold`); always go through this helper rather than constructing
`ImageFont.truetype` directly, otherwise text measurements at the same
nominal size will silently disagree with the rendered output.

**Frame is part of the layout contract.** `render._draw_frame` paints an
outer rounded black hairline plus red bead trim plus a corner glyph in
each corner. The constants `FRAME_OUTER`, `FRAME_BEAD_INSET`, and
`FRAME_PAD` define the keep-out region for text — header `y = FRAME_PAD`
and footer `y = HEIGHT - FRAME_PAD - 13` reference it directly. Resizing
text or moving the frame in isolation will produce clipping; adjust both.

**Per-theme tweaks.** The `accent` config (`heart` / `star` / `balloon`)
controls the glyphs flanking the name row, the corner glyphs, and whether
the footer gets an accent. The heart theme intentionally uses plain red
dots in the frame corners (not small hearts) and omits the footer accent —
small hearts lost their shape at 4 px and the row reads cleaner without
one. See the `accent == "heart"` branches in `_draw_frame` and `render`.

**Hero layout depends on `age_format`.** The `format` config knob
(`extended` / `days` / `hours`) reaches `render()` as `age_format` and
picks between two hero baselines: `HERO_Y_TWO_LINE = 33` for `extended`
(years/months hero with a days/hours sub line at `y=68`) and
`HERO_Y_ONE_LINE = 47` for the single-total `days` / `hours` modes
(centered vertically for the 28pt hero). The hero font auto-shrinks in
2pt steps down to 16pt if the string would overflow `WIDTH - 28`; preserve
that shrink loop when changing strings, since "31756 hours" already lands
near the limit.

## Configuration

`config.example.toml` is the canonical schema. The installer copies it to
`/etc/kidage/config.toml` (`Environment=KIDAGE_CONFIG=…` in the unit). The
TOML loader rejects naïve datetimes — `kid.born_at` must include an offset
(e.g. `2022-09-12T03:47:00-07:00`); age math is timezone-aware end-to-end
and assumes the offset matches the family's wall clock.

## Scheduling

`systemd/kidage.timer` fires every hour, all day (`OnCalendar=*-*-*
*:00:00`). The wake-window enforcement lives in `kidage.__main__`: it
compares `now.hour` to `cfg.wake_hour`/`cfg.sleep_hour` (both inclusive)
and exits 0 without touching the panel when outside the window. This
keeps `/etc/kidage/config.toml` as the single source of truth for the
schedule — editing the timer is no longer required to change waking
hours. `--preview` deliberately bypasses the window so layout work works
at any hour.

**`now` must come from the system timezone, not `cfg.born_at.tzinfo`.**
The TOML offset is whatever was in effect when the birth was saved
(e.g. `-07:00` for a summer birth), which is a fixed offset, not a
zoneinfo. Comparing `now.hour` against config hours using that offset
silently drifts by an hour across DST in observing regions. The
entrypoint uses `datetime.now().astimezone()` so the Pi's zoneinfo (set
via `timedatectl set-timezone`) drives wall-clock semantics; don't
"simplify" that back to `tz=cfg.born_at.tzinfo`.

`Persistent=true` means a Pi that boots mid-day catches up exactly once
instead of waiting for the next top of the hour; keep that flag or
hourly catch-up regressions become hard to spot. `AccuracySec=1min` lets
`systemd` batch with other timers, which matters on a Zero 2 because
waking SPI takes a non-trivial fraction of a watt — so does spawning
Python every hour for the no-op slots, but the cost is dwarfed by the
SPI-active hours and the simpler "edit one TOML file" UX wins.

## Vendored code

`vendor/waveshare_epd/` is a verbatim copy of `epd2in13b_V4.py` and
`epdconfig.py` from `waveshareteam/e-Paper`. Don't edit these files; if a
fix is needed, wrap it in `kidage/display.py`.

## Adding tests

Tests live under `tests/`. Render-side tests import `kidage.render`
directly, which is hardware-free. `tests/test_display.py` does import
`kidage.display`, but only after stubbing `vendor.waveshare_epd` in
`sys.modules` — the lazy `from vendor.waveshare_epd import epd2in13b_V4`
inside `show()` then resolves to the stub, so `RPi.GPIO` / `spidev` are
never loaded. Reuse the `monkeypatch.setitem(sys.modules, …)` fixture in
that file if you need to exercise `display.show` again.

Use `compose_preview(black, red)` to get an RGB image, or check
`image.tobytes()` for inked pixels — `Image.getdata()` is deprecated in
Pillow 14.

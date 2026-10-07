# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Raspberry Pi Zero 2 W appliance that renders a kid's age onto a Waveshare
2.13" b/w/r e-paper (V4, 250×122). A `systemd` timer runs `python -m beanclock`
hourly; each run is a oneshot that loads the TOML config, computes the age,
paints two PIL bitmaps, pushes them to the panel, sleeps the panel, and exits.
There is no daemon.

`__main__.py` → `config.load` → `age.compute` → `special.detect` →
`render.render` → either `--preview` PNG or `display.show`. `render` is
hardware-free and fully tested; `display.py` holds all hardware access.

## Commands

```bash
pip install -e '.[dev]'
pytest                       # whole suite is hardware-free
ruff check . && python -m mypy   # CI runs both
python -m beanclock --config config.example.toml --preview /tmp/p.png \
    --now 2026-04-27T07:47:00-07:00   # add --after-hours / --quiet to force those layouts
# On the Pi:
sudo bash scripts/install.sh
sudo systemctl start beanclock.service && journalctl -u beanclock.service -f
```

## Rules

- **Image planes.** `render()` returns two mode-`"1"` images at 250×122. In
  *both* planes `0` means ink. To draw red, paint `fill=0` on the red plane.
  Black ink masks red on the panel, so after-hours inversion must clear black
  wherever red has ink.
- **Lazy hardware import.** `display.show` imports `vendor.waveshare_epd`
  inside the function so tests never load `spidev`/`gpiozero`. Don't move it
  to module scope.
- **`epd.sleep()` always runs** (in `finally:`), even after a failed or
  timed-out `init()`, and its own failure must not replace the original
  error.
- **Timeout budgets.** If you change `INIT_/REFRESH_/SLEEP_TIMEOUT_SEC` in
  `display.py`, keep `TimeoutStartSec` in `systemd/beanclock.service` above
  their sum.
- **Fonts.** Always go through `render._font(size, weight)`; constructing
  `ImageFont.truetype` directly makes measurements disagree with output.
- **Frame keep-out.** `FRAME_OUTER`, `FRAME_BEAD_INSET`, `FRAME_PAD` bound
  the text area; moving text or frame alone causes clipping. Preserve the
  hero (28→16pt) and header (20→14pt) shrink loops when changing strings.
- **Accents.** `VALID_ACCENTS` in `config.py` is the source of truth; keep
  `_draw_frame`, the name-row branches in `render`, and the README spread in
  lockstep.
- **Strict config.** Every TOML table rejects unknown keys. Adding a knob
  means updating `config.example.toml`, the dataclass, and the
  `_reject_unknown` allow-list.
- **Time zones.** The live `now` must carry a `ZoneInfo` from
  `_system_zone()`. Don't "simplify" to `datetime.now().astimezone()` or
  `cfg.born_at.tzinfo`; both are fixed offsets and break DST. Age math is
  wall-clock (see `age.compute`).
- **Wake window lives in config**, not the timer: `__main__` exits early
  outside `[wake_hour, sleep_hour]`. `--preview` bypasses it, and `--now`
  previews never auto-invert or go quiet.
- **State files** live in `BEANCLOCK_STATE_DIR` (default `/var/lib/beanclock`):
  `last-clear` (once-a-day `epd.Clear()`; delete to force one) and
  `last-quiet` (missed-sleep_hour catch-up).
- **`VERSION_FILE_CANDIDATES` order matters**: `/opt/beanclock/VERSION` first,
  because the installer does a non-editable install. `tests/test_main.py`
  pins this.
- **Vendored code.** Never edit `vendor/waveshare_epd/`; wrap fixes in
  `beanclock/display.py`.

## Tests

- `tests/test_display.py` stubs `vendor.waveshare_epd` in `sys.modules`;
  reuse that fixture to exercise `display.show`. Timeout tests use
  `StuckBusyEPD` and monkeypatch the `*_TIMEOUT_SEC` constant down to 1.
- In `tests/test_main.py`, use `_freeze_now` and `_capture_render` to assert
  on the flags `main()` passes to `render()`. Don't compare two images that
  also differ for unrelated reasons (a different hour or date); that passes
  even when the feature is broken.
- Use `compose_preview(black, red)` or `image.tobytes()` to inspect pixels;
  `Image.getdata()` is deprecated.

## Writing docs and comments

The reason for a change goes in the commit message. A code comment gets at
most ~3 lines of non-obvious *why*, at the point of use; no issue numbers or
history. This file holds only rules that span files or would be easy to
break. Don't append a paragraph per feature, and delete text when the code
it describes changes.

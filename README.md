# jubilant-tribble — kid age e-paper display

[![CI](https://github.com/gkoch02/jubilant-tribble/actions/workflows/ci.yml/badge.svg)](https://github.com/gkoch02/jubilant-tribble/actions/workflows/ci.yml)

A tiny appliance: a Raspberry Pi Zero W 2 driving a Waveshare 2.13"
black/white/red e-paper (V4) shows how old your kiddo is, broken down into
years / months / days / hours. It refreshes once an hour during waking hours
and rests overnight.

![preview — heart accent, extended format](docs/preview.png)

The `display.accent` and `display.format` knobs change the border trim and how
the age is spelled out. A spread:

| Star corners, total days | Balloon corners, total hours |
| --- | --- |
| ![star accent, days format](docs/preview-star-days.png) | ![balloon accent, hours format](docs/preview-balloon-hours.png) |

## Features

- Beautiful, legible, playful layout — rounded **Fredoka** type, two-color
  accents (heart / star / balloon), no fussy clipart.
- Hourly refresh during a configurable wake window (default 07:00–21:00 local
  time), driven by a `systemd` timer that fires every hour and a wake-window
  check in the script itself — edit `/etc/kidage/config.toml` to change the
  hours, no timer reload needed.
- Special-day takeovers: on the kid's birthday the hero row reads "Happy Nth
  Birthday!", and on configurable day-count milestones (default 100 / 500 /
  1000 / 2000 / 5000) it reads "N days!" — the standard "Y years M months"
  phrasing slides to the sub line.
- Single TOML config file for the kid's name, birth datetime+timezone, wake
  window, and accent glyph.
- Once-a-day full clear to suppress ghosting; the other ~14 daily refreshes
  go straight to `display()` for less flicker.
- Pure-Python, vendored Waveshare driver — no apt-time setup beyond Pillow's
  runtime libs.

## Hardware

- Raspberry Pi Zero W 2 (any 64-bit Pi running Raspberry Pi OS Bookworm
  works).
- Waveshare 2.13" e-Paper HAT, **B/R V4** (3-color, 250×122). The HAT's pin
  header drops directly onto the Pi's GPIO. SPI must be enabled
  (`sudo raspi-config` → Interface Options → SPI). The installer does this
  for you.

## Quick start

On a fresh Pi OS Lite SD card:

```bash
git clone https://github.com/<you>/jubilant-tribble.git
cd jubilant-tribble
sudo timedatectl set-timezone America/Los_Angeles  # use your tz (zoneinfo, not an offset)
sudo bash scripts/install.sh
sudo $EDITOR /etc/kidage/config.toml         # set name + birth datetime
sudo systemctl start kidage.service          # first refresh now
systemctl list-timers kidage.timer           # confirm next hourly fire
```

`wake_hour` and `sleep_hour` are interpreted against the Pi's system
timezone, so it must be a real zoneinfo (e.g. `America/Los_Angeles`) for
the wake window to track DST correctly.

The installer creates `kidage` system user, builds a virtualenv at
`/opt/kidage/.venv`, copies the `systemd` units, enables SPI, and starts the
timer.

## Configuration

`config.example.toml`:

```toml
[kid]
name = "Lily"
# Local wall-clock time of birth, with timezone offset.
born_at = 2022-09-12T03:47:00-07:00

[schedule]
wake_hour  = 7    # inclusive, local time of first daily update
sleep_hour = 21   # inclusive, local time of last daily update

[display]
flip   = false      # rotate 180° if the ribbon comes out the other side
accent = "heart"    # heart | star | balloon
format = "extended" # extended (years/months + days/hours) | days | hours

[special_days]
birthday   = true                          # hero swaps to "Happy Nth Birthday!"
milestones = [100, 500, 1000, 2000, 5000]  # hero swaps to "N days!"; [] disables
```

On a matching day the hero row is replaced and the standard age phrasing
slides to the sub line, regardless of `display.format`. Feb 29 births
celebrate Feb 28 in non-leap years; if a milestone happens to fall on the
birthday, the birthday wins.

Edit `/etc/kidage/config.toml` and run `sudo systemctl start kidage.service`
to push the change to the panel immediately (the manual refresh still
respects `wake_hour`/`sleep_hour`, so widen those first if you're testing
outside waking hours). The next scheduled refresh will also pick up the
change.

## Development without hardware

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

pytest                                       # 76 tests, no panel needed
python -m kidage --config config.example.toml --preview /tmp/p.png
xdg-open /tmp/p.png                          # eyeball the layout
```

`--now 2026-04-27T07:00:00-07:00` lets you simulate any moment without
touching the system clock.

## Repo layout

```
kidage/                       # package
  age.py                      # AgeBreakdown + dateutil-based compute()
  config.py                   # TOML loader + validation
  render.py                   # Pillow → (black plane, red plane)
  display.py                  # thin wrapper around the vendored driver
  special.py                  # birthday + milestone detection
  __main__.py                 # entrypoint: load → render → display | --preview
vendor/waveshare_epd/         # vendored from waveshareteam/e-Paper
fonts/Fredoka.ttf             # SIL OFL variable font
systemd/kidage.{service,timer}
scripts/install.sh            # idempotent installer
tests/                        # pure-Python (no panel)
```

## Troubleshooting

- **`journalctl -u kidage.service` shows `RuntimeError: Failed to add edge
  detection`** — SPI is not enabled or the user is not in the `spi`/`gpio`
  groups. Re-run the installer.
- **Display is upside down** — set `flip = true` in `config.toml`.
- **Ghosting** — the daily clear at the first wake-hour fire wipes residual
  burn-in. Force one with `sudo rm /var/lib/kidage/last-clear && sudo
  systemctl start kidage.service`.
- **Wake window fires an hour late after a DST change** — the Pi's system
  timezone is set to a fixed offset (e.g. `Etc/GMT+7`) instead of a
  zoneinfo. Run `timedatectl status` to check, then
  `sudo timedatectl set-timezone America/Los_Angeles` (or your IANA zone)
  so the OS handles DST.

## Licenses

- `kidage/`, `tests/`, `scripts/`, `systemd/` — MIT (see `LICENSE`).
- `vendor/waveshare_epd/` — MIT, © Waveshare.
- `fonts/Fredoka.ttf` — SIL Open Font License 1.1, see `fonts/OFL.txt`.

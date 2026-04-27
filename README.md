# jubilant-tribble — kid age e-paper display

[![CI](https://github.com/gkoch02/jubilant-tribble/actions/workflows/ci.yml/badge.svg)](https://github.com/gkoch02/jubilant-tribble/actions/workflows/ci.yml)

A tiny appliance: a Raspberry Pi Zero W 2 driving a Waveshare 2.13"
black/white/red e-paper (V4) shows how old your kiddo is, broken down into
years / months / days / hours. It refreshes once an hour during waking hours
and rests overnight.

![preview](docs/preview.png)

## Features

- Beautiful, legible, playful layout — rounded **Fredoka** type, two-color
  accents (heart / star / balloon), no fussy clipart.
- Hourly refresh from 07:00–21:00 (configurable), driven by a `systemd` timer.
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
sudo bash scripts/install.sh
sudo $EDITOR /etc/kidage/config.toml         # set name + birth datetime
sudo systemctl start kidage.service          # first refresh now
systemctl list-timers kidage.timer           # confirm next hourly fire
```

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
flip   = false    # rotate 180° if the ribbon comes out the other side
accent = "heart"  # heart | star | balloon
```

Edit `/etc/kidage/config.toml` and run `sudo systemctl start kidage.service`
to push the change to the panel immediately. The next scheduled refresh will
also pick up the change.

## Development without hardware

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

pytest                                       # 18 tests, no panel needed
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

## Licenses

- `kidage/`, `tests/`, `scripts/`, `systemd/` — MIT (see `LICENSE`).
- `vendor/waveshare_epd/` — MIT, © Waveshare.
- `fonts/Fredoka.ttf` — SIL Open Font License 1.1, see `fonts/OFL.txt`.

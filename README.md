# BeanClock

[![CI](https://github.com/gkoch02/BeanClock/actions/workflows/ci.yml/badge.svg)](https://github.com/gkoch02/BeanClock/actions/workflows/ci.yml)
[![CodeQL](https://github.com/gkoch02/BeanClock/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/gkoch02/BeanClock/actions/workflows/github-code-scanning/codeql)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-C51A4A?logo=raspberrypi&logoColor=white)](https://www.raspberrypi.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

A tiny appliance: a Raspberry Pi Zero 2 W driving a Waveshare 2.13"
black/white/red e-paper (V4) shows how old your kiddo is, broken down into
years / months / days / hours. It refreshes once an hour during waking hours
and rests overnight.

![preview — heart accent, extended format](docs/preview.png)

The `display.accent` and `display.format` knobs change the border trim and how
the age is spelled out. A spread:

| Star corners, total days | Balloon corners, total hours | Heart corners, full layout |
| --- | --- | --- |
| ![star accent, days format](docs/preview-star-days.png) | ![balloon accent, hours format](docs/preview-balloon-hours.png) | ![heart accent, full format](docs/preview-heart-full.png) |

| Moon corners | Sun corners | Flower corners |
| --- | --- | --- |
| ![moon accent](docs/preview-moon.png) | ![sun accent](docs/preview-sun.png) | ![flower accent](docs/preview-flower.png) |

## What it does

The layout is rounded **Fredoka** type in black with a red accent at the
corners (heart, star, balloon, moon, sun or flower). A `systemd` timer fires
every hour; the script itself checks the wake window (07:00–21:00 local time
by default) and exits outside it, so changing the hours in
`/etc/beanclock/config.toml` needs no timer reload. The first refresh of the
day is a full clear to suppress ghosting; the rest go straight to `display()`
for less flicker.

On the kid's birthday the hero row reads "Happy Nth Birthday!", and on
day-count milestones (100, 500, 1000, 2000 and 5000 by default) it reads
"N days!", with the usual "Y years M months" sliding to the sub line.

After sunset and before sunrise, computed from your `latitude`/`longitude`
with a built-in NOAA algorithm, the black plane inverts to white-on-black so
the panel reads more comfortably in a dark room; red accents stay red. The
inversion only runs within the wake window. The last refresh of the day, at
`sleep_hour`, drops the days/hours sub line and the `full` layout's totals so
the panel doesn't sit overnight showing yesterday's hour count; if the Pi was
off at that hour, the first run after boot paints that quiet layout once.

Every e-paper call (init, refresh, sleep) runs under its own deadline, so a
stuck BUSY pin fails the run within a bounded time instead of hanging the
service and blocking later refreshes. The panel is always put back to sleep,
even after a failed init or refresh.

## Hardware

A Raspberry Pi Zero 2 W (any 64-bit Pi on Raspberry Pi OS Bookworm works; the
Zero 2 W is the cheapest fit), a Waveshare 2.13" e-Paper HAT in the **B/W/R,
V4** revision (250×122; earlier revisions use a different controller and the
vendored driver won't talk to them), a microSD card of 8 GB or more, and a
5 V micro-B supply. The HAT's 40-pin header seats straight onto the Pi's
GPIO, with no soldering. SPI must be enabled; `scripts/install.sh` does that
(`sudo raspi-config` → Interface Options → SPI by hand).

## Quick start

On a fresh Pi OS Lite SD card:

```bash
git clone https://github.com/gkoch02/BeanClock.git
cd BeanClock
sudo timedatectl set-timezone America/Los_Angeles  # use your tz (zoneinfo, not an offset)
sudo bash scripts/install.sh
sudo $EDITOR /etc/beanclock/config.toml      # set name + birth datetime
sudo systemctl start beanclock.service       # first refresh now
systemctl list-timers beanclock.timer        # confirm next hourly fire
```

`wake_hour` and `sleep_hour` are interpreted against the Pi's system
timezone, so it must be a real zoneinfo (e.g. `America/Los_Angeles`) for
the wake window to track DST correctly.

The installer creates the `beanclock` system user, installs `python3-venv`
and Pillow's runtime libraries from apt, builds a virtualenv at
`/opt/beanclock/.venv`, copies the `systemd` units, enables SPI, and starts
the timer. The Waveshare driver is vendored, so nothing else is needed.

## Configuration

Annotated, with the same values as `config.example.toml`:

```toml
[kid]
name = "Bean"
# Local wall-clock time of birth, with timezone offset.
born_at = 2023-03-14T09:00:00-07:00

[schedule]
wake_hour  = 7    # inclusive, local time of first daily update
sleep_hour = 21   # inclusive, local time of last daily update

[display]
flip               = false      # rotate 180° if the ribbon comes out the other side
accent             = "heart"    # heart | star | balloon | moon | sun | flower
format             = "extended" # extended (years/months + days/hours) | days | hours | full
after_hours_invert = true       # invert to white-on-black while dark out (requires [location])

[location]
# Decimal degrees — used to compute today's sunrise/sunset for
# after_hours_invert. Omit this whole block (and set after_hours_invert =
# false) to disable.
latitude  = 40.0150
longitude = -105.2705

[special_days]
birthday   = true                          # hero swaps to "Happy Nth Birthday!"
milestones = [100, 500, 1000, 2000, 5000]  # hero swaps to "N days!"; [] disables
```

Every table in the config is strict: a typo'd key (`wake_hours = 8`,
`layout = "full"`) or a quoted boolean (`flip = "false"`) fails at load time
instead of silently rendering the wrong thing.

On a matching day the hero row is replaced and the standard age phrasing
slides to the sub line, regardless of `display.format`. Feb 29 births
celebrate Feb 28 in non-leap years; if a milestone happens to fall on the
birthday, the birthday wins.

The `born_at` offset pins the absolute moment of birth, but the
years/months/days/hours breakdown is computed against the Pi's system
zoneinfo, so the daily flip stays on the same wall-clock minute across
DST transitions. If the Pi moves zones the actual instant of birth is
preserved and its projection follows along — a Pacific-born kid on an
Eastern Pi sees the day flip three hours later in local time, not at the
old Pacific minute.

Edit `/etc/beanclock/config.toml` and run `sudo systemctl start beanclock.service`
to push the change to the panel immediately (the manual refresh still
respects `wake_hour`/`sleep_hour`, so widen those first if you're testing
outside waking hours). The next scheduled refresh will also pick up the
change.

## Development without hardware

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

pytest                                       # full suite is hardware-free
python -m beanclock --config config.example.toml --preview /tmp/p.png
xdg-open /tmp/p.png                          # eyeball the layout
```

`--now 2026-04-27T07:00:00-07:00` lets you simulate any moment without
touching the system clock. `--after-hours` forces the inverted
(white-on-black) look and `--quiet` the last-refresh-of-the-day layout, for
layout work without waiting for sunset; combine them with `--now` for
deterministic screenshots.

## Troubleshooting

- **`journalctl -u beanclock.service` shows `RuntimeError: Failed to add edge
  detection`** — SPI is not enabled or the user is not in the `spi`/`gpio`
  groups. Re-run the installer.
- **Display is upside down** — set `flip = true` in `config.toml`.
- **`DisplayTimeoutError` naming `epd.init()` or the refresh** — the panel
  never released its BUSY pin. Usually a poorly seated ribbon cable or a
  failing panel; reseat the HAT and the FPC connector.
- **`DisplayTimeoutError` naming `epd.sleep()`** — a wedged SPI write, since
  `sleep()` never waits on BUSY; look at the SPI device rather than the
  ribbon cable.
- **Ghosting** — the daily clear at the first wake-hour fire wipes residual
  burn-in. Force one with `sudo rm /var/lib/beanclock/last-clear && sudo
  systemctl start beanclock.service`.
- **Wake window fires an hour late after a DST change** — the Pi's system
  timezone is set to a fixed offset (e.g. `Etc/GMT+7`) instead of a
  zoneinfo. Run `timedatectl status` to check, then
  `sudo timedatectl set-timezone America/Los_Angeles` (or your IANA zone)
  so the OS handles DST.
- **What's running on this Pi?** — `beanclock --version` prints the package
  version plus the git revision recorded by `install.sh` (e.g.
  `beanclock 0.1.0 (v0.1.0-3-gabc1234-dirty)`). The installer writes this to
  `/opt/beanclock/VERSION` on every run, so re-running it after a `git pull`
  is enough to refresh the stamp.

## Licenses

- Everything in this repository except the two items below — MIT (see `LICENSE`).
- `vendor/waveshare_epd/` — MIT, © Waveshare.
- `beanclock/fonts/Fredoka.ttf` — SIL Open Font License 1.1, see `beanclock/fonts/OFL.txt`.

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from PIL import Image

STATE_DIR = Path(os.environ.get("KIDAGE_STATE_DIR", "/var/lib/kidage"))
LAST_CLEAR_FILE = STATE_DIR / "last-clear"
LAST_QUIET_FILE = STATE_DIR / "last-quiet"


def _should_clear_today(today: date) -> bool:
    try:
        stamp = LAST_CLEAR_FILE.read_text().strip()
    except FileNotFoundError:
        return True
    return stamp != today.isoformat()


def _record_clear(today: date) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LAST_CLEAR_FILE.write_text(today.isoformat())


def quiet_refreshed_since(cutoff: date) -> bool:
    """True if a quiet-layout refresh has been recorded on/after `cutoff`.

    Backs the missed-sleep_hour catch-up in __main__: if the Pi was off at
    sleep_hour, the panel is frozen overnight on volatile metrics, so a boot
    later that night should paint the quiet layout exactly once.
    """
    try:
        recorded = date.fromisoformat(LAST_QUIET_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return False
    return recorded >= cutoff


def record_quiet(today: date) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LAST_QUIET_FILE.write_text(today.isoformat())


def show(black: Image.Image, red: Image.Image, today: date | None = None) -> None:
    from vendor.waveshare_epd import epd2in13b_V4

    today = today or date.today()
    epd = epd2in13b_V4.EPD()
    epd.init()
    try:
        if _should_clear_today(today):
            epd.Clear()
            _record_clear(today)
        epd.display(epd.getbuffer(black), epd.getbuffer(red))
    finally:
        # sleep() is the only call that drops the panel's drive voltage and
        # releases SPI/GPIO (epdconfig.module_exit). Tri-color panels must
        # not be left at high voltage, so it runs even when display fails.
        epd.sleep()

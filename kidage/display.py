from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from PIL import Image


STATE_DIR = Path(os.environ.get("KIDAGE_STATE_DIR", "/var/lib/kidage"))
LAST_CLEAR_FILE = STATE_DIR / "last-clear"


def _should_clear_today(today: date) -> bool:
    try:
        stamp = LAST_CLEAR_FILE.read_text().strip()
    except FileNotFoundError:
        return True
    return stamp != today.isoformat()


def _record_clear(today: date) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LAST_CLEAR_FILE.write_text(today.isoformat())


def show(black: Image.Image, red: Image.Image, today: date | None = None) -> None:
    from vendor.waveshare_epd import epd2in13b_V4

    today = today or date.today()
    epd = epd2in13b_V4.EPD()
    epd.init()
    if _should_clear_today(today):
        epd.Clear()
        _record_clear(today)
    epd.display(epd.getbuffer(black), epd.getbuffer(red))
    epd.sleep()

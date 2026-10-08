from __future__ import annotations

import logging
import os
import signal
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import FrameType

from PIL import Image

log = logging.getLogger(__name__)

STATE_DIR = Path(os.environ.get("BEANCLOCK_STATE_DIR", "/var/lib/beanclock"))
LAST_CLEAR_FILE = STATE_DIR / "last-clear"
LAST_QUIET_FILE = STATE_DIR / "last-quiet"

# The vendored busy() spins on the BUSY pin with no timeout, so a stuck panel
# would hang this oneshot and every later timer run. Keep TimeoutStartSec in
# systemd/beanclock.service above the sum of these.
INIT_TIMEOUT_SEC = 30
REFRESH_TIMEOUT_SEC = 60
SLEEP_TIMEOUT_SEC = 10


class DisplayTimeoutError(RuntimeError):
    """A blocking EPD hardware call exceeded its deadline (stuck BUSY pin?)."""


class DisplayInitError(RuntimeError):
    """epd.init() returned its documented failure code (-1)."""


@contextmanager
def _deadline(seconds: int, what: str) -> Iterator[None]:
    """Bound a blocking hardware call with SIGALRM (POSIX-only)."""

    def _on_alarm(signum: int, frame: FrameType | None) -> None:
        raise DisplayTimeoutError(
            f"{what} did not complete within {seconds}s (stuck BUSY pin?)"
        )

    previous = signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


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
    """True if a quiet-layout refresh has been recorded on/after `cutoff`."""
    try:
        recorded = date.fromisoformat(LAST_QUIET_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return False
    return recorded >= cutoff


def record_quiet(today: date) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LAST_QUIET_FILE.write_text(today.isoformat())


def show(black: Image.Image, red: Image.Image, today: date) -> None:
    from vendor.waveshare_epd import epd2in13b_V4

    epd = epd2in13b_V4.EPD()
    error: BaseException | None = None
    try:
        with _deadline(INIT_TIMEOUT_SEC, "epd.init()"):
            rc = epd.init()
        if rc == -1:  # the vendored driver's failure sentinel
            raise DisplayInitError("epd.init() returned -1 (hardware init failed)")
        with _deadline(REFRESH_TIMEOUT_SEC, "e-paper refresh"):
            if _should_clear_today(today):
                epd.Clear()
                _record_clear(today)
            epd.display(epd.getbuffer(black), epd.getbuffer(red))
    except BaseException as exc:
        error = exc
        raise
    finally:
        # Always sleep: it's the only call that drops the panel's drive
        # voltage and releases SPI/GPIO, which init() claims before it can
        # fail or time out.
        try:
            with _deadline(SLEEP_TIMEOUT_SEC, "epd.sleep()"):
                epd.sleep()
        except Exception:
            # Don't let a secondary sleep() failure replace the original error.
            if error is None:
                raise
            log.exception(
                "epd.sleep() also failed while handling %r; suppressing "
                "the sleep() failure to preserve the original error",
                error,
            )

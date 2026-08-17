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

STATE_DIR = Path(os.environ.get("KIDAGE_STATE_DIR", "/var/lib/kidage"))
LAST_CLEAR_FILE = STATE_DIR / "last-clear"
LAST_QUIET_FILE = STATE_DIR / "last-quiet"

# The vendored driver's busy() (vendor/waveshare_epd/epd2in13b_V4.py) spins
# on the BUSY pin with no timeout of its own — a stuck/faulty panel would
# otherwise hang this oneshot service forever, blocking every future hourly
# timer run. Each of these bounds one phase of the hardware call sequence;
# systemd/kidage.service sets TimeoutStartSec comfortably above their sum as
# defense in depth. init()/display() go through busy() several times each
# (SWRESET, register writes, the refresh itself) so they get the larger
# budgets; sleep() only sends DEEP_SLEEP + a fixed 2s delay and doesn't poll
# BUSY at all, but it's still bounded in case a flaky panel wedges the SPI
# write itself.
INIT_TIMEOUT_SEC = 30
REFRESH_TIMEOUT_SEC = 60
SLEEP_TIMEOUT_SEC = 10


class DisplayTimeoutError(RuntimeError):
    """A blocking EPD hardware call exceeded its bounded deadline.

    The most likely cause is a permanently-asserted BUSY pin (stuck/faulty
    panel, bad ribbon cable, etc.) — the vendored driver's busy() loop has
    no timeout of its own.
    """


class DisplayInitError(RuntimeError):
    """epd.init() returned its documented failure code (-1)."""


@contextmanager
def _deadline(seconds: int, what: str) -> Iterator[None]:
    """Bound a blocking hardware call with SIGALRM.

    POSIX-only by design — this appliance only ever runs on Linux (Pi Zero W
    2), same assumption the rest of the hardware path already makes.
    """

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
    error: BaseException | None = None
    try:
        with _deadline(INIT_TIMEOUT_SEC, "epd.init()"):
            rc = epd.init()
        # module_init() (wrapped by epd.init()) returns non-zero on failure
        # per the vendored driver's own convention; -1 is its documented
        # sentinel. Silently continuing would paint into an uninitialized
        # panel and typically just surfaces as a confusing later failure.
        if rc == -1:
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
        # sleep() is the only call that drops the panel's drive voltage and
        # releases SPI/GPIO (epdconfig.module_exit). Tri-color panels must
        # not be left at high voltage, so it runs even when init/display
        # failed or timed out — module_init() (called inside epd.init())
        # opens SPI/GPIO before any BUSY-pin wait, so those resources are
        # already claimed by the time init() could time out, and still need
        # releasing. It gets its own bounded deadline too: sleep() doesn't
        # poll BUSY, but a wedged SPI write shouldn't be able to hang the
        # service either.
        try:
            with _deadline(SLEEP_TIMEOUT_SEC, "epd.sleep()"):
                epd.sleep()
        except Exception:
            # If init()/display() already failed, sleep()'s own SPI traffic
            # can fail too (e.g. an unopened bus) — don't let that secondary
            # failure silently replace the original, more useful error.
            if error is None:
                raise
            log.exception(
                "epd.sleep() also failed while handling %r; suppressing "
                "the sleep() failure to preserve the original error",
                error,
            )

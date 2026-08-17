import importlib
import sys
import time
from datetime import date
from types import SimpleNamespace

import pytest
from PIL import Image


@pytest.fixture
def display(monkeypatch, tmp_path):
    """Reload kidage.display with KIDAGE_STATE_DIR pointed at tmp_path."""
    monkeypatch.setenv("KIDAGE_STATE_DIR", str(tmp_path))
    sys.modules.pop("kidage.display", None)
    mod = importlib.import_module("kidage.display")
    yield mod
    sys.modules.pop("kidage.display", None)


def test_should_clear_when_state_missing(display, tmp_path):
    assert not (tmp_path / "last-clear").exists()
    assert display._should_clear_today(date(2026, 4, 27)) is True


def test_should_not_clear_when_already_recorded_today(display):
    today = date(2026, 4, 27)
    display._record_clear(today)
    assert display._should_clear_today(today) is False


def test_should_clear_when_recorded_date_is_stale(display):
    display._record_clear(date(2026, 4, 27))
    assert display._should_clear_today(date(2026, 4, 28)) is True


def test_record_clear_creates_state_dir(display, tmp_path):
    target = tmp_path / "nested-state"
    display.STATE_DIR = target
    display.LAST_CLEAR_FILE = target / "last-clear"
    display._record_clear(date(2026, 4, 27))
    assert (target / "last-clear").read_text() == "2026-04-27"


class FakeEPD:
    def __init__(self):
        self.calls: list[str] = []

    def init(self):
        self.calls.append("init")
        return 0

    def Clear(self):
        self.calls.append("Clear")

    def getbuffer(self, img):
        self.calls.append(f"getbuffer:{img.mode}")
        return b"buf"

    def display(self, black_buf, red_buf):
        self.calls.append(f"display({black_buf!r},{red_buf!r})")

    def sleep(self):
        self.calls.append("sleep")


def _install_fake_epd(monkeypatch, fake):
    """Wire `fake` up as the vendor.waveshare_epd.epd2in13b_V4.EPD() the
    lazy import inside display.show() resolves to."""
    module = SimpleNamespace(EPD=lambda: fake)
    pkg = SimpleNamespace(epd2in13b_V4=module)
    monkeypatch.setitem(sys.modules, "vendor.waveshare_epd", pkg)
    monkeypatch.setitem(sys.modules, "vendor.waveshare_epd.epd2in13b_V4", module)
    return fake


@pytest.fixture
def fake_epd_module(monkeypatch):
    return _install_fake_epd(monkeypatch, FakeEPD())


def _planes():
    return Image.new("1", (250, 122), 1), Image.new("1", (250, 122), 1)


def test_show_first_run_calls_clear_and_records(display, fake_epd_module, tmp_path):
    black, red = _planes()
    display.show(black, red, today=date(2026, 4, 27))

    assert fake_epd_module.calls == [
        "init",
        "Clear",
        "getbuffer:1",
        "getbuffer:1",
        "display(b'buf',b'buf')",
        "sleep",
    ]
    assert (tmp_path / "last-clear").read_text() == "2026-04-27"


def test_show_second_run_same_day_skips_clear(display, fake_epd_module):
    black, red = _planes()
    today = date(2026, 4, 27)
    display.show(black, red, today=today)
    fake_epd_module.calls.clear()

    display.show(black, red, today=today)
    assert "Clear" not in fake_epd_module.calls
    assert fake_epd_module.calls[0] == "init"
    assert fake_epd_module.calls[-1] == "sleep"


def test_show_next_day_clears_again(display, fake_epd_module):
    black, red = _planes()
    display.show(black, red, today=date(2026, 4, 27))
    fake_epd_module.calls.clear()

    display.show(black, red, today=date(2026, 4, 28))
    assert "Clear" in fake_epd_module.calls


def test_show_always_sleeps_last(display, fake_epd_module):
    """Forgetting epd.sleep() will slowly burn the panel — pin it."""
    black, red = _planes()
    display.show(black, red, today=date(2026, 4, 27))
    assert fake_epd_module.calls[-1] == "sleep"


def test_show_today_none_defaults_to_date_today(display, fake_epd_module, tmp_path, monkeypatch):
    """show() accepts today=None and falls back to date.today(); the
    last-clear file should land on the real current date."""
    fake_today = date(2026, 7, 4)

    class FakeDate(date):
        @classmethod
        def today(cls):
            return fake_today

    monkeypatch.setattr("kidage.display.date", FakeDate)
    black, red = _planes()
    display.show(black, red)
    assert (tmp_path / "last-clear").read_text() == "2026-07-04"


def test_should_clear_when_state_file_is_empty(display, tmp_path):
    """A truncated state file (e.g. crash mid-write) reads as empty; we want
    the next refresh to clear, not skip — pin the defensive behavior."""
    (tmp_path / "last-clear").write_text("")
    assert display._should_clear_today(date(2026, 4, 27)) is True


def test_should_clear_when_state_file_is_malformed(display, tmp_path):
    """A state file with non-ISO content (manual edit, encoding drift) must
    not crash _should_clear_today; it should just clear."""
    (tmp_path / "last-clear").write_text("yesterday\n")
    assert display._should_clear_today(date(2026, 4, 27)) is True


def test_show_sleeps_even_when_display_raises(display, fake_epd_module):
    """sleep() is the only call that drops the panel's drive voltage and
    releases SPI/GPIO; a failed display() must not skip it."""
    fake_epd_module.display = lambda *_: (_ for _ in ()).throw(RuntimeError("spi"))
    black, red = _planes()
    with pytest.raises(RuntimeError, match="spi"):
        display.show(black, red, today=date(2026, 4, 27))
    assert fake_epd_module.calls[-1] == "sleep"


def test_show_sleeps_even_when_clear_raises(display, fake_epd_module):
    fake_epd_module.Clear = lambda: (_ for _ in ()).throw(RuntimeError("spi"))
    black, red = _planes()
    with pytest.raises(RuntimeError, match="spi"):
        display.show(black, red, today=date(2026, 4, 27))
    assert fake_epd_module.calls[-1] == "sleep"


def test_quiet_refreshed_since_missing_file(display):
    assert display.quiet_refreshed_since(date(2026, 4, 27)) is False


def test_quiet_record_and_read_roundtrip(display, tmp_path):
    display.record_quiet(date(2026, 4, 27))
    assert (tmp_path / "last-quiet").read_text() == "2026-04-27"
    assert display.quiet_refreshed_since(date(2026, 4, 27)) is True
    assert display.quiet_refreshed_since(date(2026, 4, 26)) is True
    assert display.quiet_refreshed_since(date(2026, 4, 28)) is False


def test_quiet_refreshed_since_malformed_file(display, tmp_path):
    """A truncated/garbled state file must read as 'not refreshed' so the
    catch-up paints once rather than crashing or skipping forever."""
    (tmp_path / "last-quiet").write_text("last tuesday\n")
    assert display.quiet_refreshed_since(date(2026, 4, 27)) is False


class StuckBusyEPD(FakeEPD):
    """Simulates a permanently-asserted BUSY pin: whichever hardware call is
    named in `hang_call` spins forever, mirroring the vendored driver's
    unbounded `busy()` loop (vendor/waveshare_epd/epd2in13b_V4.py)."""

    def __init__(self, hang_call: str):
        super().__init__()
        self._hang_call = hang_call

    def _record_and_maybe_hang(self, key: str, logged: str | None = None):
        self.calls.append(logged if logged is not None else key)
        if key == self._hang_call:
            while True:  # pragma: no branch - broken out of by SIGALRM
                time.sleep(0.01)

    def init(self):
        self._record_and_maybe_hang("init")
        return 0

    def Clear(self):
        self._record_and_maybe_hang("Clear")

    def display(self, black_buf, red_buf):
        self._record_and_maybe_hang(
            "display", logged=f"display({black_buf!r},{red_buf!r})"
        )

    def sleep(self):
        self._record_and_maybe_hang("sleep")


def test_show_raises_on_stuck_busy_during_init(display, monkeypatch):
    """A panel wedged before/during epd.init() (e.g. SWRESET never clears
    BUSY) must fail within INIT_TIMEOUT_SEC rather than hanging forever."""
    monkeypatch.setattr(display, "INIT_TIMEOUT_SEC", 1)
    fake = _install_fake_epd(monkeypatch, StuckBusyEPD(hang_call="init"))
    black, red = _planes()
    with pytest.raises(display.DisplayTimeoutError, match="init"):
        display.show(black, red, today=date(2026, 4, 27))
    # module_init() (inside epd.init()) opens SPI/GPIO before any BUSY wait,
    # so even a stuck init still needs the finally-block sleep() to release
    # them.
    assert fake.calls[-1] == "sleep"


def test_show_raises_on_stuck_busy_during_display(display, monkeypatch):
    """A panel wedged mid-refresh (ondisplay()'s busy() wait) must fail
    within REFRESH_TIMEOUT_SEC, and sleep() must still run afterward."""
    monkeypatch.setattr(display, "REFRESH_TIMEOUT_SEC", 1)
    fake = _install_fake_epd(monkeypatch, StuckBusyEPD(hang_call="display"))
    black, red = _planes()
    with pytest.raises(display.DisplayTimeoutError, match="refresh"):
        display.show(black, red, today=date(2026, 4, 27))
    assert fake.calls[-1] == "sleep"


def test_show_sleep_call_is_itself_bounded(display, monkeypatch):
    """sleep() doesn't poll BUSY, but a wedged SPI write there shouldn't be
    able to hang the service either — it gets its own deadline."""
    monkeypatch.setattr(display, "SLEEP_TIMEOUT_SEC", 1)
    fake = _install_fake_epd(monkeypatch, StuckBusyEPD(hang_call="sleep"))
    black, red = _planes()
    with pytest.raises(display.DisplayTimeoutError, match="sleep"):
        display.show(black, red, today=date(2026, 4, 27))
    assert fake.calls[-1] == "sleep"


def test_show_rejects_init_return_of_minus_one(display, fake_epd_module):
    """epd.init() returning -1 is the vendored driver's documented failure
    sentinel (module_init() != 0); it must not be silently treated as
    success."""

    def failing_init():
        fake_epd_module.calls.append("init")
        return -1

    fake_epd_module.init = failing_init
    black, red = _planes()
    with pytest.raises(display.DisplayInitError):
        display.show(black, red, today=date(2026, 4, 27))
    # sleep() is the invariant that must never be skipped, even on an init
    # failure — SPI/GPIO were already opened by module_init() by this point.
    assert fake_epd_module.calls[-1] == "sleep"


def test_show_preserves_init_error_when_sleep_also_fails(
    display, fake_epd_module, caplog
):
    """If epd.init() returns -1 (module_init() failed) *and* the cleanup
    sleep() call also raises (e.g. an unopened SPI bus), the caller must
    still see the original DisplayInitError, not the secondary sleep()
    failure masking it."""

    def failing_init():
        fake_epd_module.calls.append("init")
        return -1

    def failing_sleep():
        fake_epd_module.calls.append("sleep")
        raise OSError("SPI bus not open")

    fake_epd_module.init = failing_init
    fake_epd_module.sleep = failing_sleep
    black, red = _planes()
    with pytest.raises(display.DisplayInitError):
        display.show(black, red, today=date(2026, 4, 27))
    # sleep() must still have been attempted, even though it also failed.
    assert fake_epd_module.calls[-1] == "sleep"


def test_show_succeeds_when_init_returns_zero(display, fake_epd_module):
    """Sanity check: the normal init() return value (0) must not be
    mistaken for the failure sentinel."""
    black, red = _planes()
    display.show(black, red, today=date(2026, 4, 27))
    assert fake_epd_module.calls[-1] == "sleep"
    assert "init" in fake_epd_module.calls

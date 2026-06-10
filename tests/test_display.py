import importlib
import sys
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

    def Clear(self):
        self.calls.append("Clear")

    def getbuffer(self, img):
        self.calls.append(f"getbuffer:{img.mode}")
        return b"buf"

    def display(self, black_buf, red_buf):
        self.calls.append(f"display({black_buf!r},{red_buf!r})")

    def sleep(self):
        self.calls.append("sleep")


@pytest.fixture
def fake_epd_module(monkeypatch):
    fake = FakeEPD()
    module = SimpleNamespace(EPD=lambda: fake)
    pkg = SimpleNamespace(epd2in13b_V4=module)
    monkeypatch.setitem(sys.modules, "vendor.waveshare_epd", pkg)
    monkeypatch.setitem(sys.modules, "vendor.waveshare_epd.epd2in13b_V4", module)
    return fake


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

import logging
import os
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from PIL import Image

import beanclock.render
from beanclock.__main__ import (
    VERSION_FILE_CANDIDATES,
    _default_config_path,
    _deployed_revision,
    _system_zone,
    _version_string,
    main,
)
from beanclock.age import compute
from beanclock.render import HEIGHT, WIDTH

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_CONFIG = REPO_ROOT / "config.example.toml"
PT = timezone(timedelta(hours=-7))
KID = '[kid]\nname = "Lily"\nborn_at = 2022-09-12T03:47:00-07:00\n'
SCHEDULE = '[schedule]\nwake_hour = 7\nsleep_hour = 21\n'


def _write_config(tmp_path: Path, body: str) -> Path:
    cfg = tmp_path / "config.toml"
    cfg.write_text(body)
    return cfg


def _after_hours_config(tmp_path: Path) -> Path:
    return _write_config(
        tmp_path,
        KID + SCHEDULE
        + '[display]\nafter_hours_invert = true\n'
        + '[location]\nlatitude = 40.0150\nlongitude = -105.2705\n',
    )


def _simple_live_config(tmp_path: Path) -> Path:
    return _write_config(tmp_path, KID + SCHEDULE + '[display]\nformat = "full"\n')


def _display():
    # Imported per call: test_display.py reloads this module, and main()'s
    # lazy import must see the same object these helpers patch.
    import beanclock.display
    return beanclock.display


def _called_show(monkeypatch) -> list[tuple]:
    """Patch display.show with a recorder and return the call list."""
    calls: list[tuple] = []

    def fake_show(black, red, today):
        calls.append((black, red, today))

    monkeypatch.setattr(_display(), "show", fake_show)
    return calls


def _state_in_tmp(monkeypatch, tmp_path):
    """Keep live-path state files (last-clear / last-quiet) out of /var/lib."""
    display = _display()
    monkeypatch.setattr(display, "STATE_DIR", tmp_path)
    monkeypatch.setattr(display, "LAST_CLEAR_FILE", tmp_path / "last-clear")
    monkeypatch.setattr(display, "LAST_QUIET_FILE", tmp_path / "last-quiet")


def _capture_render(monkeypatch) -> dict:
    """Wrap render() so a test can read what main() passed it. Positional
    args land under "args"; keyword args under their own names."""
    captured: dict = {}

    def fake_render(*args, **kwargs):
        captured.update(kwargs, args=args)
        return beanclock.render.render(*args, **kwargs)
    monkeypatch.setattr("beanclock.__main__.render", fake_render)
    return captured


def _freeze_now(monkeypatch, frozen):
    """Pin main()'s wall clock to `frozen` (naive; tz comes from _system_zone)."""
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen.replace(tzinfo=tz)
    monkeypatch.setattr("beanclock.__main__.datetime", FrozenDateTime)


def _live_pacific(monkeypatch, tmp_path, frozen) -> list[tuple]:
    """Set up a live (no --now) run at `frozen` Pacific time with display.show
    recorded and state files in tmp_path. Returns the show() call list."""
    monkeypatch.setattr("beanclock.__main__._system_zone", lambda: PT)
    _freeze_now(monkeypatch, frozen)
    _state_in_tmp(monkeypatch, tmp_path)
    return _called_show(monkeypatch)


def _fake_etc(monkeypatch, tmp_path, *, localtime=None, timezone_file=None):
    """Redirect _system_zone's /etc/localtime and /etc/timezone lookups."""
    real_path = Path
    paths = {
        "/etc/localtime": localtime or tmp_path / "missing-localtime",
        "/etc/timezone": timezone_file or tmp_path / "missing-timezone",
    }
    monkeypatch.setattr(
        "beanclock.__main__.Path", lambda arg: paths.get(arg) or real_path(arg)
    )


def _localtime_symlink(tmp_path, zone: str) -> Path:
    tzdata = tmp_path / "zoneinfo" / zone
    tzdata.parent.mkdir(parents=True)
    tzdata.write_bytes(b"")
    link = tmp_path / "localtime"
    os.symlink(tzdata, link)
    return link


def test_preview_writes_png_at_panel_size(tmp_path):
    out = tmp_path / "preview.png"
    rc = main([
        "--config", str(EXAMPLE_CONFIG),
        "--preview", str(out),
        "--now", "2026-04-27T07:47:00-07:00",
    ])
    assert rc == 0
    assert out.exists()

    img = Image.open(out)
    assert img.size == (WIDTH, HEIGHT)
    assert img.mode == "RGB"


def test_preview_renders_three_inks(tmp_path):
    """Black ink, red ink, and white background must all appear."""
    out = tmp_path / "preview.png"
    main([
        "--config", str(EXAMPLE_CONFIG),
        "--preview", str(out),
        "--now", "2026-04-27T07:47:00-07:00",
    ])
    colors = {c for _, c in Image.open(out).getcolors(maxcolors=10)}
    assert (0, 0, 0) in colors
    assert (220, 30, 30) in colors
    assert (255, 255, 255) in colors


def test_preview_is_deterministic_for_pinned_now(tmp_path):
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    args = [
        "--config", str(EXAMPLE_CONFIG),
        "--now", "2026-04-27T07:47:00-07:00",
    ]
    main(args + ["--preview", str(a)])
    main(args + ["--preview", str(b)])
    assert a.read_bytes() == b.read_bytes()


def test_default_config_path_prefers_env(monkeypatch, tmp_path):
    target = tmp_path / "from-env.toml"
    monkeypatch.setenv("BEANCLOCK_CONFIG", str(target))
    assert _default_config_path() == target


def test_default_config_path_falls_back_to_local(monkeypatch, tmp_path):
    monkeypatch.delenv("BEANCLOCK_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.toml").write_text("")
    assert _default_config_path() == Path("config.toml")


def test_default_config_path_falls_back_to_etc(monkeypatch, tmp_path):
    monkeypatch.delenv("BEANCLOCK_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    assert _default_config_path() == Path("/etc/beanclock/config.toml")


def test_main_invokes_display_when_no_preview(monkeypatch):
    """Without --preview, main() should hand the planes to display.show."""
    calls = _called_show(monkeypatch)
    rc = main([
        "--config", str(EXAMPLE_CONFIG),
        "--now", "2026-04-27T07:47:00-07:00",
    ])
    assert rc == 0
    [(black, red, today)] = calls
    assert black.size == (WIDTH, HEIGHT)
    assert red.size == (WIDTH, HEIGHT)
    assert today.isoformat() == "2026-04-27"


@pytest.mark.parametrize(("now", "shows"), [
    ("2026-04-27T06:59:00-07:00", 0),  # before wake_hour
    ("2026-04-27T07:00:00-07:00", 1),  # wake_hour is inclusive
    ("2026-04-27T21:30:00-07:00", 1),  # sleep_hour is inclusive
    ("2026-04-27T22:00:00-07:00", 0),  # after sleep_hour
])
def test_main_respects_wake_window(monkeypatch, now, shows):
    calls = _called_show(monkeypatch)
    assert main(["--config", str(EXAMPLE_CONFIG), "--now", now]) == 0
    assert len(calls) == shows


def test_system_zone_reads_localtime_symlink(tmp_path, monkeypatch):
    # Most distros ship /etc/localtime as a symlink into /usr/share/zoneinfo.
    _fake_etc(
        monkeypatch, tmp_path,
        localtime=_localtime_symlink(tmp_path, "America/Los_Angeles"),
    )
    assert _system_zone() == ZoneInfo("America/Los_Angeles")


def test_system_zone_falls_back_to_etc_timezone(tmp_path, monkeypatch):
    # Some Debian-likes write the IANA name to /etc/timezone instead.
    tz_file = tmp_path / "timezone"
    tz_file.write_text("America/New_York\n")
    _fake_etc(monkeypatch, tmp_path, timezone_file=tz_file)
    assert _system_zone() == ZoneInfo("America/New_York")


def test_system_zone_falls_back_to_utc_when_nothing_configured(tmp_path, monkeypatch):
    _fake_etc(monkeypatch, tmp_path)
    assert _system_zone() == ZoneInfo("UTC")


def test_system_zone_falls_back_when_localtime_is_a_regular_file(tmp_path, monkeypatch):
    """A copied (not symlinked) tzdata blob has no zone name to read; with no
    /etc/timezone alongside, fall back to UTC rather than guessing."""
    localtime = tmp_path / "localtime"
    localtime.write_bytes(b"\x00TZif2")
    _fake_etc(monkeypatch, tmp_path, localtime=localtime)
    assert _system_zone() == ZoneInfo("UTC")


def test_live_now_carries_dst_aware_zoneinfo(tmp_path, monkeypatch):
    # born_at is saved at fixed -08:00 and "now" is a summer anniversary in
    # America/Los_Angeles. A fixed-offset now would report 23 hours; a
    # ZoneInfo now lands on 0.
    cfg = _write_config(
        tmp_path,
        '[kid]\nname = "Lily"\nborn_at = 2024-03-09T13:54:00-08:00\n'
        + SCHEDULE + '[special_days]\nmilestones = []\n',
    )
    _fake_etc(
        monkeypatch, tmp_path,
        localtime=_localtime_symlink(tmp_path, "America/Los_Angeles"),
    )
    _freeze_now(monkeypatch, datetime(2026, 4, 9, 13, 54))
    _called_show(monkeypatch)
    _state_in_tmp(monkeypatch, tmp_path)

    captured = {}

    def fake_compute(born_at, now):
        captured["now"] = now
        return compute(born_at, now)
    monkeypatch.setattr("beanclock.__main__.compute", fake_compute)

    assert main(["--config", str(cfg)]) == 0
    now = captured["now"]
    assert now.tzinfo == ZoneInfo("America/Los_Angeles")
    age = compute(datetime.fromisoformat("2024-03-09T13:54:00-08:00"), now)
    assert (age.years, age.months, age.days, age.hours) == (2, 1, 0, 0)


def test_deployed_revision_returns_none_when_no_candidate_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "beanclock.__main__.VERSION_FILE_CANDIDATES", [tmp_path / "missing"]
    )
    assert _deployed_revision() is None


def test_deployed_revision_reads_first_existing_candidate(tmp_path, monkeypatch):
    primary = tmp_path / "primary"
    fallback = tmp_path / "fallback"
    fallback.write_text("from-fallback\n")
    monkeypatch.setattr(
        "beanclock.__main__.VERSION_FILE_CANDIDATES", [primary, fallback]
    )
    assert _deployed_revision() == "from-fallback"
    primary.write_text("from-primary\n")
    assert _deployed_revision() == "from-primary"


def test_deployed_revision_treats_empty_file_as_missing(tmp_path, monkeypatch):
    f = tmp_path / "VERSION"
    f.write_text("   \n")
    monkeypatch.setattr("beanclock.__main__.VERSION_FILE_CANDIDATES", [f])
    assert _deployed_revision() is None


def test_version_string_includes_package_version_without_revision(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "beanclock.__main__.VERSION_FILE_CANDIDATES", [tmp_path / "missing"]
    )
    s = _version_string()
    assert s.startswith("beanclock ")
    assert "(" not in s


def test_version_string_includes_revision_when_present(tmp_path, monkeypatch):
    f = tmp_path / "VERSION"
    f.write_text("v0.1.0-3-gabc1234-dirty\n")
    monkeypatch.setattr("beanclock.__main__.VERSION_FILE_CANDIDATES", [f])
    s = _version_string()
    assert "v0.1.0-3-gabc1234-dirty" in s
    assert s.startswith("beanclock ")


def test_version_string_when_package_metadata_missing(tmp_path, monkeypatch):
    """Running from a source tree that was never pip-installed."""
    from importlib import metadata

    def boom(name):
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr("beanclock.__main__.metadata.version", boom)
    monkeypatch.setattr(
        "beanclock.__main__.VERSION_FILE_CANDIDATES", [tmp_path / "missing"]
    )
    assert _version_string() == "beanclock unknown"


def test_version_flag_prints_and_exits_zero(tmp_path, monkeypatch, capsys):
    f = tmp_path / "VERSION"
    f.write_text("v0.1.0-3-gabc1234-dirty\n")
    monkeypatch.setattr("beanclock.__main__.VERSION_FILE_CANDIDATES", [f])
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "beanclock" in out
    assert "v0.1.0-3-gabc1234-dirty" in out


def test_version_candidates_include_install_dir_path():
    # A non-editable install puts __main__.py in site-packages, so the
    # __file__-relative candidate alone can't find install.sh's stamp.
    assert Path("/opt/beanclock/VERSION") in VERSION_FILE_CANDIDATES


@pytest.mark.parametrize(("verbose", "level"), [(True, logging.DEBUG), (False, logging.INFO)])
def test_verbose_flag_sets_log_level(monkeypatch, verbose, level):
    captured = {}
    monkeypatch.setattr(
        "beanclock.__main__.logging.basicConfig",
        lambda **kwargs: captured.update(kwargs),
    )
    _called_show(monkeypatch)
    args = ["--config", str(EXAMPLE_CONFIG), "--now", "2026-04-27T07:47:00-07:00"]
    assert main(args + (["-v"] if verbose else [])) == 0
    assert captured["level"] == level


def test_naive_now_is_rejected_with_clean_error(tmp_path, capsys):
    """A --now without a UTC offset must be an argparse error, not a traceback."""
    with pytest.raises(SystemExit) as excinfo:
        main([
            "--config", str(EXAMPLE_CONFIG),
            "--preview", str(tmp_path / "out.png"),
            "--now", "2026-04-27T12:00:00",
        ])
    assert excinfo.value.code == 2
    assert "offset" in capsys.readouterr().err


def test_garbage_now_is_rejected_with_clean_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as excinfo:
        main([
            "--config", str(EXAMPLE_CONFIG),
            "--preview", str(tmp_path / "out.png"),
            "--now", "yesterday",
        ])
    assert excinfo.value.code == 2
    assert "ISO 8601" in capsys.readouterr().err


def test_preview_ignores_wake_window(tmp_path, monkeypatch):
    """--preview is for layout work and must render at any hour."""
    calls = _called_show(monkeypatch)
    out = tmp_path / "preview.png"
    rc = main([
        "--config", str(EXAMPLE_CONFIG),
        "--preview", str(out),
        "--now", "2026-04-27T03:00:00-07:00",
    ])
    assert rc == 0
    assert out.exists()
    assert calls == []


@pytest.mark.parametrize(("flags", "after_hours", "quiet"), [
    ([], False, False),
    (["--after-hours"], True, False),
    (["--quiet"], False, True),
])
def test_preview_layout_flags_reach_render(tmp_path, monkeypatch, flags, after_hours, quiet):
    """--after-hours / --quiet force their layouts in previews, and only
    their own: a swapped wiring must fail here."""
    captured = _capture_render(monkeypatch)
    assert main([
        "--config", str(EXAMPLE_CONFIG),
        "--preview", str(tmp_path / "out.png"),
        "--now", "2026-04-27T12:00:00-07:00",
        *flags,
    ]) == 0
    assert captured["after_hours"] is after_hours
    assert captured["quiet"] is quiet


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (12, 0, False),
        (19, 0, False),  # look-ahead 19:30 is still before sunset
        (19, 38, True),  # look-ahead lands exactly on sunset
        (20, 0, True),   # 8 min before sunset, but most of the hour is dark
        (21, 0, True),
    ],
)
def test_live_after_hours_tracks_sunset_with_30min_lookahead(
    tmp_path, monkeypatch, hour, minute, expected
):
    cfg = _after_hours_config(tmp_path)
    fake_sunrise = datetime(2026, 5, 16, 12, 45, tzinfo=UTC)  # 05:45 PDT
    fake_sunset = datetime(2026, 5, 17, 3, 8, tzinfo=UTC)     # 20:08 PDT
    monkeypatch.setattr(
        "beanclock.solar.sun_times",
        lambda d, lat, lon: (fake_sunrise, fake_sunset),
    )
    _live_pacific(monkeypatch, tmp_path, datetime(2026, 5, 16, hour, minute))
    captured = _capture_render(monkeypatch)

    assert main(["--config", str(cfg)]) == 0
    assert captured["after_hours"] is expected


@pytest.mark.parametrize(("hour", "expected"), [
    (7, True),   # 07:30 look-ahead is before the 07:45 sunrise
    (8, False),  # 08:30 is past it
])
def test_live_after_hours_inverts_before_sunrise(tmp_path, monkeypatch, hour, expected):
    cfg = _after_hours_config(tmp_path)
    fake_sunrise = datetime(2026, 12, 21, 14, 45, tzinfo=UTC)  # 07:45 PT
    fake_sunset = datetime(2026, 12, 22, 2, 30, tzinfo=UTC)    # 19:30 PT
    monkeypatch.setattr(
        "beanclock.solar.sun_times", lambda d, lat, lon: (fake_sunrise, fake_sunset)
    )
    _live_pacific(monkeypatch, tmp_path, datetime(2026, 12, 21, hour, 0))
    captured = _capture_render(monkeypatch)

    assert main(["--config", str(cfg)]) == 0
    assert captured["after_hours"] is expected


@pytest.mark.parametrize("is_polar_night", [True, False])
def test_live_polar_sun_times_none_consults_polar_night(tmp_path, monkeypatch, is_polar_night):
    """No sunrise/sunset today: polar night inverts all day, polar day never."""
    cfg = _after_hours_config(tmp_path)
    monkeypatch.setattr("beanclock.solar.sun_times", lambda d, lat, lon: None)
    monkeypatch.setattr("beanclock.solar.polar_night", lambda d, lat, lon: is_polar_night)
    _live_pacific(monkeypatch, tmp_path, datetime(2026, 6, 21, 20, 0))
    captured = _capture_render(monkeypatch)

    assert main(["--config", str(cfg)]) == 0
    assert captured["after_hours"] is is_polar_night


def test_live_after_hours_disabled_never_inverts(tmp_path, monkeypatch):
    """Without after_hours_invert, never invert and never run the sunset calc."""
    cfg = _write_config(tmp_path, KID + SCHEDULE)

    def boom(*args, **kwargs):
        raise AssertionError("sun_times called when after-hours is off")
    monkeypatch.setattr("beanclock.solar.sun_times", boom)
    calls = _live_pacific(monkeypatch, tmp_path, datetime(2026, 4, 27, 20, 30))
    captured = _capture_render(monkeypatch)

    assert main(["--config", str(cfg)]) == 0
    assert len(calls) == 1
    assert captured["after_hours"] is False


@pytest.mark.parametrize(("hour", "quiet"), [(20, False), (21, True)])
def test_live_quiet_only_at_sleep_hour(tmp_path, monkeypatch, hour, quiet):
    """Only the sleep_hour refresh goes quiet, and it records the marker."""
    cfg = _simple_live_config(tmp_path)
    _live_pacific(monkeypatch, tmp_path, datetime(2026, 4, 27, hour, 0))
    captured = _capture_render(monkeypatch)

    assert main(["--config", str(cfg)]) == 0
    assert captured["quiet"] is quiet
    marker = tmp_path / "last-quiet"
    assert (marker.read_text() if marker.exists() else None) == ("2026-04-27" if quiet else None)


def test_main_passes_special_string_to_render_on_birthday(tmp_path, monkeypatch):
    """main() must hand render() the actual detect_special() string, not just
    some non-None placeholder."""
    cfg = _write_config(
        tmp_path, '[kid]\nname = "Lilah"\nborn_at = 2022-09-12T03:47:00-07:00\n'
    )
    captured = _capture_render(monkeypatch)
    assert main([
        "--config", str(cfg),
        "--preview", str(tmp_path / "out.png"),
        "--now", "2026-09-12T08:00:00-07:00",
    ]) == 0
    assert captured["special"] == "Happy 4th Birthday!"


def test_main_no_special_passes_none_to_render(tmp_path, monkeypatch):
    """render() branches on `special is not None`, so an ordinary refresh must
    pass None, not an empty string."""
    captured = _capture_render(monkeypatch)
    assert main([
        "--config", str(EXAMPLE_CONFIG),
        "--preview", str(tmp_path / "out.png"),
        "--now", "2026-04-27T07:47:00-07:00",
    ]) == 0
    assert captured["special"] is None


def test_missed_sleep_hour_catchup_paints_quiet_once(tmp_path, monkeypatch):
    """Pi off at 21:00, boots 22:30: paint the quiet layout once, record it,
    and skip the following hours."""
    cfg = _simple_live_config(tmp_path)
    calls = _live_pacific(monkeypatch, tmp_path, datetime(2026, 4, 27, 22, 30))
    captured = _capture_render(monkeypatch)
    assert main(["--config", str(cfg)]) == 0
    assert len(calls) == 1, "catch-up run must refresh the panel"
    assert captured["quiet"] is True
    assert (tmp_path / "last-quiet").read_text() == "2026-04-27"

    _freeze_now(monkeypatch, datetime(2026, 4, 27, 23, 0))
    assert main(["--config", str(cfg)]) == 0
    assert len(calls) == 1


def test_no_catchup_when_sleep_hour_refresh_happened(tmp_path, monkeypatch):
    cfg = _simple_live_config(tmp_path)
    calls = _live_pacific(monkeypatch, tmp_path, datetime(2026, 4, 27, 22, 30))
    (tmp_path / "last-quiet").write_text("2026-04-27")
    assert main(["--config", str(cfg)]) == 0
    assert calls == []


def test_small_hours_catchup_uses_yesterday_cutoff(tmp_path, monkeypatch):
    """After midnight the overnight image belongs to *yesterday's* sleep_hour:
    a record from yesterday counts as covered, an older one does not."""
    cfg = _simple_live_config(tmp_path)
    calls = _live_pacific(monkeypatch, tmp_path, datetime(2026, 4, 27, 2, 0))

    (tmp_path / "last-quiet").write_text("2026-04-26")
    assert main(["--config", str(cfg)]) == 0
    assert calls == []

    (tmp_path / "last-quiet").write_text("2026-04-24")
    assert main(["--config", str(cfg)]) == 0
    assert len(calls) == 1
    # The marker names the sleep_hour covered (yesterday), not now.date().
    assert (tmp_path / "last-quiet").read_text() == "2026-04-26"


def test_small_hours_catchup_then_missed_next_sleep_hour_both_catch_up(
    tmp_path, monkeypatch
):
    """Day N's 21:00 is missed and caught up at 02:00 on day N+1; day N+1's
    own 21:00 is then also missed. The 22:30 boot that night must still catch
    up rather than treat the small-hours catch-up as covering today."""
    cfg = _simple_live_config(tmp_path)
    calls = _live_pacific(monkeypatch, tmp_path, datetime(2026, 4, 27, 2, 0))
    assert main(["--config", str(cfg)]) == 0
    assert len(calls) == 1, "first catch-up must paint"
    assert (tmp_path / "last-quiet").read_text() == "2026-04-26"

    # A normal daytime render must not touch last-quiet.
    _freeze_now(monkeypatch, datetime(2026, 4, 27, 12, 0))
    assert main(["--config", str(cfg)]) == 0
    assert len(calls) == 2
    assert (tmp_path / "last-quiet").read_text() == "2026-04-26"

    _freeze_now(monkeypatch, datetime(2026, 4, 27, 22, 30))
    assert main(["--config", str(cfg)]) == 0
    assert len(calls) == 3, "second same-night catch-up must paint"
    assert (tmp_path / "last-quiet").read_text() == "2026-04-27"


def test_render_receives_zone_projected_born_at(tmp_path, monkeypatch):
    """A 23:47 -07:00 birth viewed from -04:00 projects to the next calendar
    day; the footer date must follow the age math onto it."""
    cfg = _write_config(
        tmp_path, '[kid]\nname = "Lilah"\nborn_at = 2022-09-12T23:47:00-07:00\n'
    )
    captured = _capture_render(monkeypatch)
    assert main([
        "--config", str(cfg),
        "--preview", str(tmp_path / "out.png"),
        "--now", "2026-06-10T12:00:00-04:00",
    ]) == 0
    born = captured["args"][2]
    assert (born.month, born.day) == (9, 13)

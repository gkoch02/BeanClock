import os
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

from kidage.__main__ import _default_config_path, _system_zone, main
from kidage.render import HEIGHT, WIDTH

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_CONFIG = REPO_ROOT / "config.example.toml"


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
    monkeypatch.setenv("KIDAGE_CONFIG", str(target))
    assert _default_config_path() == target


def test_default_config_path_falls_back_to_local(monkeypatch, tmp_path):
    monkeypatch.delenv("KIDAGE_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.toml").write_text("")
    assert _default_config_path() == Path("config.toml")


def test_default_config_path_falls_back_to_etc(monkeypatch, tmp_path):
    monkeypatch.delenv("KIDAGE_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    assert _default_config_path() == Path("/etc/kidage/config.toml")


def test_main_invokes_display_when_no_preview(tmp_path, monkeypatch):
    """Without --preview, main() should hand the planes to display.show."""
    captured = {}

    def fake_show(black, red, today=None):
        captured["black"] = black
        captured["red"] = red
        captured["today"] = today

    import kidage.display
    monkeypatch.setattr(kidage.display, "show", fake_show)
    # __main__ does `from kidage.display import show` inside the function,
    # so patching the module attribute is enough.

    rc = main([
        "--config", str(EXAMPLE_CONFIG),
        "--now", "2026-04-27T07:47:00-07:00",
    ])
    assert rc == 0
    assert captured["black"].size == (WIDTH, HEIGHT)
    assert captured["red"].size == (WIDTH, HEIGHT)
    assert captured["today"].isoformat() == "2026-04-27"


def _called_show(monkeypatch) -> list[tuple]:
    """Patch display.show with a recorder and return the call list."""
    calls: list[tuple] = []

    def fake_show(black, red, today=None):
        calls.append((black, red, today))

    import kidage.display
    monkeypatch.setattr(kidage.display, "show", fake_show)
    return calls


def test_main_skips_display_before_wake_hour(monkeypatch):
    calls = _called_show(monkeypatch)
    rc = main([
        "--config", str(EXAMPLE_CONFIG),
        "--now", "2026-04-27T06:59:00-07:00",
    ])
    assert rc == 0
    assert calls == []


def test_main_skips_display_after_sleep_hour(monkeypatch):
    calls = _called_show(monkeypatch)
    rc = main([
        "--config", str(EXAMPLE_CONFIG),
        "--now", "2026-04-27T22:00:00-07:00",
    ])
    assert rc == 0
    assert calls == []


def test_main_runs_at_wake_hour_inclusive(monkeypatch):
    calls = _called_show(monkeypatch)
    rc = main([
        "--config", str(EXAMPLE_CONFIG),
        "--now", "2026-04-27T07:00:00-07:00",
    ])
    assert rc == 0
    assert len(calls) == 1


def test_main_runs_at_sleep_hour_inclusive(monkeypatch):
    calls = _called_show(monkeypatch)
    rc = main([
        "--config", str(EXAMPLE_CONFIG),
        "--now", "2026-04-27T21:30:00-07:00",
    ])
    assert rc == 0
    assert len(calls) == 1


def test_main_preview_on_birthday_differs_from_normal_day(tmp_path):
    """End-to-end: a preview pinned to the kid's birthday must render a
    different image than a non-birthday preview, proving the special-day
    plumbing reaches render() through main()."""
    normal = tmp_path / "normal.png"
    bday = tmp_path / "bday.png"
    main([
        "--config", str(EXAMPLE_CONFIG),
        "--preview", str(normal),
        "--now", "2026-04-27T07:47:00-07:00",
    ])
    main([
        "--config", str(EXAMPLE_CONFIG),
        "--preview", str(bday),
        "--now", "2026-09-12T08:00:00-07:00",  # Lily's birthday
    ])
    assert normal.read_bytes() != bday.read_bytes()


def test_system_zone_reads_localtime_symlink(tmp_path, monkeypatch):
    # Most distros ship /etc/localtime as a symlink into /usr/share/zoneinfo.
    fake_tzdata = tmp_path / "zoneinfo" / "America" / "Los_Angeles"
    fake_tzdata.parent.mkdir(parents=True)
    fake_tzdata.write_bytes(b"")
    fake_localtime = tmp_path / "localtime"
    os.symlink(fake_tzdata, fake_localtime)

    real_path = Path
    def fake_path(arg):
        if arg == "/etc/localtime":
            return fake_localtime
        if arg == "/etc/timezone":
            return tmp_path / "missing-timezone"
        return real_path(arg)
    monkeypatch.setattr("kidage.__main__.Path", fake_path)

    zone = _system_zone()
    assert isinstance(zone, ZoneInfo)
    assert str(zone) == "America/Los_Angeles"


def test_system_zone_falls_back_to_etc_timezone(tmp_path, monkeypatch):
    # Some Debian-likes write the IANA name to /etc/timezone instead of (or
    # alongside) the symlink.
    fake_timezone = tmp_path / "timezone"
    fake_timezone.write_text("America/New_York\n")

    real_path = Path
    def fake_path(arg):
        if arg == "/etc/localtime":
            return tmp_path / "missing-localtime"
        if arg == "/etc/timezone":
            return fake_timezone
        return real_path(arg)
    monkeypatch.setattr("kidage.__main__.Path", fake_path)

    zone = _system_zone()
    assert isinstance(zone, ZoneInfo)
    assert str(zone) == "America/New_York"


def test_live_now_carries_dst_aware_zoneinfo(tmp_path, monkeypatch):
    # End-to-end DST regression for the live path (no --now). born_at is
    # saved at fixed -08:00 (PST when the config was written); the system
    # is in America/Los_Angeles and "now" is in summer. With a fixed-offset
    # tzinfo on now, compute would project born_at into -07:00 and report
    # 23 hours on the monthly anniversary. With a ZoneInfo, it lands at 0.
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[kid]\n'
        'name = "Lily"\n'
        'born_at = 2024-03-09T13:54:00-08:00\n'
        '[schedule]\nwake_hour = 7\nsleep_hour = 21\n'
        '[display]\nflip = false\naccent = "heart"\nformat = "extended"\n'
        '[special_days]\nbirthday = true\nmilestones = []\n'
    )

    fake_tzdata = tmp_path / "zoneinfo" / "America" / "Los_Angeles"
    fake_tzdata.parent.mkdir(parents=True)
    fake_tzdata.write_bytes(b"")
    fake_localtime = tmp_path / "localtime"
    os.symlink(fake_tzdata, fake_localtime)
    real_path = Path
    def fake_path(arg):
        if arg == "/etc/localtime":
            return fake_localtime
        if arg == "/etc/timezone":
            return tmp_path / "missing"
        return real_path(arg)
    monkeypatch.setattr("kidage.__main__.Path", fake_path)

    # Pin datetime.now to a summer anniversary moment in PDT.
    from datetime import datetime as _dt

    class FakeDateTime(_dt):
        @classmethod
        def now(cls, tz=None):
            return _dt(2026, 4, 9, 13, 54, tzinfo=tz)
    monkeypatch.setattr("kidage.__main__.datetime", FakeDateTime)

    captured = {}
    real_compute = __import__("kidage.age", fromlist=["compute"]).compute
    def fake_compute(born_at, now):
        captured["now"] = now
        return real_compute(born_at, now)
    monkeypatch.setattr("kidage.__main__.compute", fake_compute)

    # Patch display.show so the live path doesn't try to touch hardware.
    import kidage.display
    monkeypatch.setattr(kidage.display, "show", lambda *_, **__: None)

    rc = main(["--config", str(cfg)])
    assert rc == 0
    now = captured["now"]
    assert isinstance(now.tzinfo, ZoneInfo)
    assert str(now.tzinfo) == "America/Los_Angeles"

    from kidage.age import compute
    age = compute(_dt.fromisoformat("2024-03-09T13:54:00-08:00"), now)
    assert (age.years, age.months, age.days, age.hours) == (2, 1, 0, 0)


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
    assert calls == []  # preview path never touches display.show

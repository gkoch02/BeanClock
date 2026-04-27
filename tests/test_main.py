from pathlib import Path

from PIL import Image

from kidage.__main__ import _default_config_path, main
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

from datetime import timedelta
from pathlib import Path

import pytest

from kidage.config import load


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "config.toml"
    p.write_text(body)
    return p


def test_load_minimal(tmp_path):
    cfg = load(_write(tmp_path, """
[kid]
name = "Lily"
born_at = 2022-09-12T03:47:00-07:00
"""))
    assert cfg.name == "Lily"
    assert cfg.born_at.utcoffset() == timedelta(hours=-7)
    assert cfg.wake_hour == 7
    assert cfg.sleep_hour == 21
    assert cfg.flip is False
    assert cfg.accent == "heart"


def test_load_full(tmp_path):
    cfg = load(_write(tmp_path, """
[kid]
name = "Maximilian"
born_at = 2024-01-15T08:00:00+00:00

[schedule]
wake_hour = 6
sleep_hour = 22

[display]
flip = true
accent = "balloon"
"""))
    assert cfg.name == "Maximilian"
    assert cfg.wake_hour == 6
    assert cfg.sleep_hour == 22
    assert cfg.flip is True
    assert cfg.accent == "balloon"


def test_rejects_naive_born_at(tmp_path):
    p = _write(tmp_path, """
[kid]
name = "X"
born_at = 2024-01-01T00:00:00
""")
    with pytest.raises(ValueError):
        load(p)


def test_rejects_bad_schedule(tmp_path):
    p = _write(tmp_path, """
[kid]
name = "X"
born_at = 2024-01-01T00:00:00+00:00
[schedule]
wake_hour = 22
sleep_hour = 6
""")
    with pytest.raises(ValueError):
        load(p)


def test_rejects_unknown_accent(tmp_path):
    p = _write(tmp_path, """
[kid]
name = "X"
born_at = 2024-01-01T00:00:00+00:00
[display]
accent = "unicorn"
""")
    with pytest.raises(ValueError):
        load(p)


def test_age_format_defaults_to_extended(tmp_path):
    cfg = load(_write(tmp_path, """
[kid]
name = "X"
born_at = 2024-01-01T00:00:00+00:00
"""))
    assert cfg.age_format == "extended"


@pytest.mark.parametrize("value", ["days", "hours", "extended"])
def test_age_format_accepts_known_values(tmp_path, value):
    cfg = load(_write(tmp_path, f"""
[kid]
name = "X"
born_at = 2024-01-01T00:00:00+00:00
[display]
format = "{value}"
"""))
    assert cfg.age_format == value


def test_rejects_unknown_format(tmp_path):
    p = _write(tmp_path, """
[kid]
name = "X"
born_at = 2024-01-01T00:00:00+00:00
[display]
format = "weeks"
""")
    with pytest.raises(ValueError):
        load(p)

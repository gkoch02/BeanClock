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


@pytest.mark.parametrize("value", ["days", "hours", "extended", "full", "DAYS"])
def test_age_format_accepts_known_values(tmp_path, value):
    cfg = load(_write(tmp_path, f"""
[kid]
name = "X"
born_at = 2024-01-01T00:00:00+00:00
[display]
format = "{value}"
"""))
    assert cfg.age_format == value.lower()


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


def test_special_days_defaults(tmp_path):
    cfg = load(_write(tmp_path, """
[kid]
name = "X"
born_at = 2024-01-01T00:00:00+00:00
"""))
    assert cfg.birthday is True
    assert cfg.milestones == (100, 500, 1000, 2000, 5000)


def test_special_days_custom(tmp_path):
    cfg = load(_write(tmp_path, """
[kid]
name = "X"
born_at = 2024-01-01T00:00:00+00:00

[special_days]
birthday = false
milestones = [42, 7, 7, 100]
"""))
    assert cfg.birthday is False
    # Loader sorts and dedupes so render-side checks don't have to.
    assert cfg.milestones == (7, 42, 100)


def test_special_days_empty_milestones_allowed(tmp_path):
    cfg = load(_write(tmp_path, """
[kid]
name = "X"
born_at = 2024-01-01T00:00:00+00:00

[special_days]
milestones = []
"""))
    assert cfg.milestones == ()


def test_rejects_non_positive_milestone(tmp_path):
    p = _write(tmp_path, """
[kid]
name = "X"
born_at = 2024-01-01T00:00:00+00:00

[special_days]
milestones = [100, 0, 500]
""")
    with pytest.raises(ValueError):
        load(p)


def test_rejects_non_int_milestone(tmp_path):
    p = _write(tmp_path, """
[kid]
name = "X"
born_at = 2024-01-01T00:00:00+00:00

[special_days]
milestones = [100, "many", 500]
""")
    with pytest.raises(ValueError):
        load(p)


def test_rejects_non_list_milestones(tmp_path):
    p = _write(tmp_path, """
[kid]
name = "X"
born_at = 2024-01-01T00:00:00+00:00

[special_days]
milestones = 1000
""")
    with pytest.raises(ValueError):
        load(p)

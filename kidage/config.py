from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Config:
    name: str
    born_at: datetime
    wake_hour: int
    sleep_hour: int
    flip: bool
    accent: str
    age_format: str
    birthday: bool
    milestones: tuple[int, ...]


VALID_ACCENTS = {"heart", "star", "balloon"}
VALID_FORMATS = {"extended", "days", "hours"}
DEFAULT_MILESTONES: tuple[int, ...] = (100, 500, 1000, 2000, 5000)


def load(path: Path) -> Config:
    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    kid = raw["kid"]
    name = kid["name"]
    born_at = kid["born_at"]
    if not isinstance(born_at, datetime):
        raise ValueError(
            "kid.born_at must be a TOML datetime with offset, "
            "e.g. 2022-09-12T03:47:00-07:00"
        )
    if born_at.tzinfo is None:
        raise ValueError("kid.born_at must include a timezone offset")

    schedule = raw.get("schedule", {})
    wake_hour = int(schedule.get("wake_hour", 7))
    sleep_hour = int(schedule.get("sleep_hour", 21))
    if not (0 <= wake_hour < sleep_hour <= 23):
        raise ValueError("schedule must satisfy 0 <= wake_hour < sleep_hour <= 23")

    display = raw.get("display", {})
    flip = bool(display.get("flip", False))
    accent = str(display.get("accent", "heart")).lower()
    if accent not in VALID_ACCENTS:
        raise ValueError(f"display.accent must be one of {sorted(VALID_ACCENTS)}")
    age_format = str(display.get("format", "extended")).lower()
    if age_format not in VALID_FORMATS:
        raise ValueError(f"display.format must be one of {sorted(VALID_FORMATS)}")

    special = raw.get("special_days", {})
    birthday = bool(special.get("birthday", True))
    raw_milestones = special.get("milestones", list(DEFAULT_MILESTONES))
    if not isinstance(raw_milestones, list) or not all(
        isinstance(m, int) and not isinstance(m, bool) and m > 0 for m in raw_milestones
    ):
        raise ValueError("special_days.milestones must be a list of positive integers")
    milestones = tuple(sorted(set(raw_milestones)))

    return Config(
        name=name,
        born_at=born_at,
        wake_hour=wake_hour,
        sleep_hour=sleep_hour,
        flip=flip,
        accent=accent,
        age_format=age_format,
        birthday=birthday,
        milestones=milestones,
    )

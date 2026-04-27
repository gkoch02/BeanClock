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


VALID_ACCENTS = {"heart", "star", "balloon"}


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

    return Config(
        name=name,
        born_at=born_at,
        wake_hour=wake_hour,
        sleep_hour=sleep_hour,
        flip=flip,
        accent=accent,
    )

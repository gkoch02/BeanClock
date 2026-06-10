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
    after_hours_invert: bool
    birthday: bool
    milestones: tuple[int, ...]
    latitude: float | None
    longitude: float | None


VALID_ACCENTS = {"heart", "star", "balloon", "moon", "sun", "flower"}
VALID_FORMATS = {"extended", "days", "hours", "full"}
DEFAULT_MILESTONES: tuple[int, ...] = (100, 500, 1000, 2000, 5000)


def _reject_unknown(table: dict[str, object], where: str, allowed: set[str]) -> None:
    # Every table is strict so a typo'd key fails at load time instead of
    # silently rendering the default (e.g. `wake_hours = 8` leaving the wake
    # window at 7).
    unknown = set(table) - allowed
    if unknown:
        raise ValueError(
            f"unknown key(s) {where}: {sorted(unknown)}; "
            f"valid keys are {sorted(allowed)}"
        )


def load(path: Path) -> Config:
    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    _reject_unknown(
        raw,
        "at the top level",
        {"kid", "schedule", "display", "location", "special_days"},
    )

    kid = raw.get("kid")
    if not isinstance(kid, dict):
        raise ValueError("config must have a [kid] section with 'name' and 'born_at'")
    _reject_unknown(kid, "under [kid]", {"name", "born_at"})
    if "name" not in kid:
        raise ValueError("kid.name is required")
    if "born_at" not in kid:
        raise ValueError("kid.born_at is required")
    name = kid["name"]
    if not isinstance(name, str) or not name.strip():
        raise ValueError("kid.name must be a non-empty string")
    born_at = kid["born_at"]
    if not isinstance(born_at, datetime):
        raise ValueError(
            "kid.born_at must be a TOML datetime with offset, "
            "e.g. 2022-09-12T03:47:00-07:00"
        )
    if born_at.tzinfo is None:
        raise ValueError("kid.born_at must include a timezone offset")
    if born_at > datetime.now(tz=born_at.tzinfo):
        raise ValueError(
            "kid.born_at is in the future — the kiddo isn't here yet"
        )

    schedule = raw.get("schedule", {})
    _reject_unknown(schedule, "under [schedule]", {"wake_hour", "sleep_hour"})
    wake_hour = int(schedule.get("wake_hour", 7))
    sleep_hour = int(schedule.get("sleep_hour", 21))
    if not (0 <= wake_hour < sleep_hour <= 23):
        raise ValueError("schedule must satisfy 0 <= wake_hour < sleep_hour <= 23")

    display = raw.get("display", {})
    _reject_unknown(display, "under [display]", {"flip", "accent", "format", "after_hours_invert"})
    flip = bool(display.get("flip", False))
    accent = str(display.get("accent", "heart")).lower()
    if accent not in VALID_ACCENTS:
        raise ValueError(f"display.accent must be one of {sorted(VALID_ACCENTS)}")
    age_format = str(display.get("format", "extended")).lower()
    if age_format not in VALID_FORMATS:
        raise ValueError(f"display.format must be one of {sorted(VALID_FORMATS)}")
    after_hours_invert = bool(display.get("after_hours_invert", False))

    location = raw.get("location", {})
    _reject_unknown(location, "under [location]", {"latitude", "longitude"})
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    if (latitude is None) != (longitude is None):
        raise ValueError(
            "location.latitude and location.longitude must be set together"
        )
    if latitude is not None:
        latitude = float(latitude)
        longitude = float(longitude)
        if not -90.0 <= latitude <= 90.0:
            raise ValueError("location.latitude must be in [-90, 90]")
        if not -180.0 <= longitude <= 180.0:
            raise ValueError("location.longitude must be in [-180, 180]")
    if after_hours_invert and latitude is None:
        raise ValueError(
            "display.after_hours_invert requires [location] latitude/longitude"
        )

    special = raw.get("special_days", {})
    _reject_unknown(special, "under [special_days]", {"birthday", "milestones"})
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
        after_hours_invert=after_hours_invert,
        birthday=birthday,
        milestones=milestones,
        latitude=latitude,
        longitude=longitude,
    )

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from dateutil.relativedelta import relativedelta


@dataclass(frozen=True)
class AgeBreakdown:
    years: int
    months: int
    days: int
    hours: int
    total_days: int
    total_hours: int


def compute(born_at: datetime, now: datetime) -> AgeBreakdown:
    if born_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("born_at and now must be timezone-aware")
    if now < born_at:
        raise ValueError("now is before born_at; the kiddo isn't here yet")
    # Wall-clock semantics: project both into now's zone and strip tzinfo so
    # DST doesn't shift the anniversary by an hour twice a year.
    born_local = born_at.astimezone(now.tzinfo).replace(tzinfo=None)
    now_local = now.replace(tzinfo=None)
    rd = relativedelta(now_local, born_local)
    delta = now_local - born_local
    return AgeBreakdown(
        rd.years,
        rd.months,
        rd.days,
        rd.hours,
        total_days=delta.days,
        total_hours=int(delta.total_seconds() // 3600),
    )


def pluralize(n: int, unit: str) -> str:
    return f"{n} {unit}" if n == 1 else f"{n} {unit}s"

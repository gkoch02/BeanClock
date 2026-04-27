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
    rd = relativedelta(now, born_at)
    delta = now - born_at
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

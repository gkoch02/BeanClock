from __future__ import annotations

import calendar
from collections.abc import Sequence
from datetime import datetime

from kidage.age import AgeBreakdown, pluralize

_ORDINAL_SUFFIXES = {1: "st", 2: "nd", 3: "rd"}


def _is_birthday(born_at: datetime, now: datetime) -> bool:
    if born_at.month == now.month and born_at.day == now.day:
        return True
    # Feb 29 birth: celebrate on Feb 28 in non-leap years. In leap years the
    # real Feb 29 hits the equality check above, and we explicitly skip Feb 28
    # so the kid only gets one birthday that year.
    if born_at.month == 2 and born_at.day == 29 and now.month == 2 and now.day == 28:
        return not calendar.isleap(now.year)
    return False


def _ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{_ORDINAL_SUFFIXES.get(n % 10, 'th')}"


def detect(
    born_at: datetime,
    now: datetime,
    age: AgeBreakdown,
    *,
    birthday: bool,
    milestones: Sequence[int],
) -> str | None:
    if birthday and _is_birthday(born_at, now):
        # Use the calendar-year delta, not age.years: age.years only ticks over
        # at the exact birth minute, so a kid born at 18:00 would otherwise see
        # "Happy 3rd Birthday!" on the morning of their 4th birthday.
        years_turning = now.year - born_at.year
        if years_turning > 0:
            return f"Happy {_ordinal(years_turning)} Birthday!"
        return "Happy Birthday!"
    if age.total_days in milestones:
        return f"{pluralize(age.total_days, 'day')}!"
    return None

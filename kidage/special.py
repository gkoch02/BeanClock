from __future__ import annotations

import calendar
from datetime import datetime
from typing import Sequence

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
        if age.years > 0:
            return f"Happy {_ordinal(age.years)} Birthday!"
        return "Happy Birthday!"
    if age.total_days in milestones:
        return f"{pluralize(age.total_days, 'day')}!"
    return None

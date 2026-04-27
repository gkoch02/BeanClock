from datetime import datetime, timezone, timedelta

import pytest

from kidage.age import AgeBreakdown, compute, pluralize


PT = timezone(timedelta(hours=-7))


def test_basic_age():
    born = datetime(2022, 9, 12, 3, 47, tzinfo=PT)
    now = datetime(2026, 4, 27, 7, 47, tzinfo=PT)
    assert compute(born, now) == AgeBreakdown(3, 7, 15, 4)


def test_exact_birthday_minute():
    born = datetime(2022, 9, 12, 3, 47, tzinfo=PT)
    now = datetime(2024, 9, 12, 3, 47, tzinfo=PT)
    assert compute(born, now) == AgeBreakdown(2, 0, 0, 0)


def test_one_hour_old():
    born = datetime(2026, 4, 27, 6, 0, tzinfo=PT)
    now = datetime(2026, 4, 27, 7, 0, tzinfo=PT)
    assert compute(born, now) == AgeBreakdown(0, 0, 0, 1)


def test_leap_day_birth():
    # Born Feb 29; in non-leap years dateutil rolls to Feb 28.
    born = datetime(2020, 2, 29, 12, 0, tzinfo=PT)
    now = datetime(2023, 3, 1, 12, 0, tzinfo=PT)
    age = compute(born, now)
    assert age.years == 3
    assert age.months == 0


def test_month_edge():
    # Born Jan 31; one month later is "Feb 28/29".
    born = datetime(2024, 1, 31, 0, 0, tzinfo=PT)
    now = datetime(2024, 2, 29, 0, 0, tzinfo=PT)  # 2024 is leap
    assert compute(born, now) == AgeBreakdown(0, 1, 0, 0)


def test_requires_tz():
    naive = datetime(2024, 1, 1)
    with pytest.raises(ValueError):
        compute(naive, datetime.now(tz=PT))


def test_rejects_future_birth():
    born = datetime(2030, 1, 1, tzinfo=PT)
    now = datetime(2026, 4, 27, tzinfo=PT)
    with pytest.raises(ValueError):
        compute(born, now)


def test_pluralize():
    assert pluralize(0, "year") == "0 years"
    assert pluralize(1, "year") == "1 year"
    assert pluralize(2, "year") == "2 years"

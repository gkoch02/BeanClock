from datetime import UTC, date, datetime, timedelta, timezone

from kidage.solar import sun_times

PDT = timezone(timedelta(hours=-7))
PST = timezone(timedelta(hours=-8))


def _within(actual: datetime, expected: datetime, tolerance_seconds: int) -> bool:
    return abs((actual - expected).total_seconds()) <= tolerance_seconds


def test_san_jose_summer_solstice():
    """NOAA solar calculator gives San Jose, CA on 2026-06-21:
    sunrise ~05:48 PDT, sunset ~20:32 PDT. Allow 2 minutes of slack
    against the simplified equation."""
    sunrise, sunset = sun_times(date(2026, 6, 21), 37.2872, -121.9500)
    assert _within(
        sunrise.astimezone(PDT),
        datetime(2026, 6, 21, 5, 48, tzinfo=PDT),
        120,
    )
    assert _within(
        sunset.astimezone(PDT),
        datetime(2026, 6, 21, 20, 32, tzinfo=PDT),
        120,
    )


def test_san_jose_winter_solstice():
    """Pin the other extreme: 2026-12-21 sunrise ~07:18 PST,
    sunset ~16:53 PST. Catches sign errors in the declination math
    that summer alone wouldn't surface."""
    sunrise, sunset = sun_times(date(2026, 12, 21), 37.2872, -121.9500)
    assert _within(
        sunrise.astimezone(PST),
        datetime(2026, 12, 21, 7, 18, tzinfo=PST),
        120,
    )
    assert _within(
        sunset.astimezone(PST),
        datetime(2026, 12, 21, 16, 53, tzinfo=PST),
        120,
    )


def test_returns_utc_aware_datetimes():
    sunrise, sunset = sun_times(date(2026, 4, 27), 37.2872, -121.9500)
    assert sunrise.tzinfo is UTC
    assert sunset.tzinfo is UTC
    assert sunrise < sunset


def test_polar_day_returns_none():
    """80°N at midsummer: the sun never sets, so there's no sunrise or
    sunset to return. The render path treats None as 'feature off for
    today' rather than crashing."""
    assert sun_times(date(2026, 6, 21), 80.0, 0.0) is None


def test_polar_night_returns_none():
    """80°N at midwinter: the sun never rises."""
    assert sun_times(date(2026, 12, 21), 80.0, 0.0) is None


def test_equator_equinox_is_roughly_twelve_hours():
    """At the equator on either equinox, day and night are each ~12 hours.
    Allow generous slack for the equation-of-time wobble."""
    sunrise, sunset = sun_times(date(2026, 3, 20), 0.0, 0.0)
    daylight = (sunset - sunrise).total_seconds()
    assert abs(daylight - 12 * 3600) < 600  # within 10 minutes

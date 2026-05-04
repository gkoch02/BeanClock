"""Sunrise/sunset for the after-hours inversion feature.

NOAA's simplified solar-position equation, written out longhand to avoid
adding a runtime dependency. Accurate to roughly a minute outside polar
regions, which is well within the once-per-hour cadence of the kidage
refresh.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta

# J2000 epoch is noon UTC on 2000-01-01; all subsequent math is in days
# relative to this anchor.
_J2000 = datetime(2000, 1, 1, 12, 0, 0, tzinfo=UTC)
# Apparent solar disk + standard atmospheric refraction at the horizon
# (NOAA convention).
_HORIZON_DEG = -0.83
# Earth's axial tilt (obliquity of the ecliptic).
_OBLIQUITY_DEG = 23.4397


def sun_times(
    d: date, lat: float, lon: float
) -> tuple[datetime, datetime] | None:
    """Return (sunrise_utc, sunset_utc) for date `d` at (lat, lon).

    Returns None during polar day or polar night (the sun never crosses the
    horizon at the given latitude/date).
    """
    # Days from J2000 (noon UT on 2000-01-01) to mean solar noon on date `d`
    # at this longitude. (Solar noon at longitude L happens lon/360 days
    # before noon UT, with east positive.)
    n = (d - _J2000.date()).days - lon / 360.0

    # Solar mean anomaly (degrees).
    M = (357.5291 + 0.98560028 * n) % 360.0
    M_rad = math.radians(M)

    # Equation of center.
    C = (
        1.9148 * math.sin(M_rad)
        + 0.0200 * math.sin(2 * M_rad)
        + 0.0003 * math.sin(3 * M_rad)
    )

    # Apparent ecliptic longitude.
    lam = (M + C + 180.0 + 102.9372) % 360.0
    lam_rad = math.radians(lam)

    # Solar transit (Julian-day offset of solar noon).
    j_transit = n + 0.0053 * math.sin(M_rad) - 0.0069 * math.sin(2 * lam_rad)

    # Sun declination.
    sin_decl = math.sin(lam_rad) * math.sin(math.radians(_OBLIQUITY_DEG))
    decl_rad = math.asin(sin_decl)

    # Hour angle: how far before/after solar noon the disk crosses the horizon.
    lat_rad = math.radians(lat)
    cos_omega = (
        math.sin(math.radians(_HORIZON_DEG)) - math.sin(lat_rad) * sin_decl
    ) / (math.cos(lat_rad) * math.cos(decl_rad))
    if cos_omega < -1.0 or cos_omega > 1.0:
        return None
    omega_deg = math.degrees(math.acos(cos_omega))

    sunrise = _J2000 + timedelta(days=j_transit - omega_deg / 360.0)
    sunset = _J2000 + timedelta(days=j_transit + omega_deg / 360.0)
    return sunrise, sunset

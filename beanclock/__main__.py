from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from importlib import metadata
from pathlib import Path
from zoneinfo import ZoneInfo

from beanclock.age import compute
from beanclock.config import load
from beanclock.render import compose_preview, render
from beanclock.special import detect as detect_special

log = logging.getLogger("beanclock")

# install.sh writes /opt/beanclock/VERSION. The installer's non-editable install
# puts __file__ in site-packages, so the relative path is the `pip install -e .`
# fallback only.
VERSION_FILE_CANDIDATES = [
    Path("/opt/beanclock/VERSION"),
    Path(__file__).resolve().parent.parent / "VERSION",
]


def _default_config_path() -> Path:
    env = os.environ.get("BEANCLOCK_CONFIG")
    if env:
        return Path(env)
    local = Path("config.toml")
    if local.exists():
        return local
    return Path("/etc/beanclock/config.toml")


def _deployed_revision() -> str | None:
    """Return the git revision recorded by install.sh, or None if absent."""
    for path in VERSION_FILE_CANDIDATES:
        if path.is_file():
            return path.read_text().strip() or None
    return None


def _version_string() -> str:
    try:
        pkg = metadata.version("beanclock")
    except metadata.PackageNotFoundError:
        pkg = "unknown"
    rev = _deployed_revision()
    return f"beanclock {pkg} ({rev})" if rev else f"beanclock {pkg}"


def _system_zone() -> ZoneInfo:
    # A ZoneInfo, not datetime.now().astimezone(): that returns a fixed offset
    # for the current moment, which can't replay a winter birth's offset in
    # summer, so the anniversary would slip an hour across DST.
    p = Path("/etc/localtime")
    if p.is_symlink():
        target = os.readlink(p)
        marker = "zoneinfo/"
        idx = target.rfind(marker)
        if idx >= 0:
            return ZoneInfo(target[idx + len(marker):])
    tz_file = Path("/etc/timezone")
    if tz_file.exists():
        return ZoneInfo(tz_file.read_text().strip())
    return ZoneInfo("UTC")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="beanclock")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=(
            "Path to TOML config (env: BEANCLOCK_CONFIG; "
            "default: ./config.toml or /etc/beanclock/config.toml)."
        ),
    )
    parser.add_argument(
        "--preview",
        type=Path,
        default=None,
        help="Skip the e-paper and write a PNG preview to this path instead.",
    )
    parser.add_argument(
        "--now",
        type=str,
        default=None,
        help="Override the current time (ISO 8601 with offset). Useful for previews.",
    )
    parser.add_argument(
        "--after-hours",
        action="store_true",
        help=(
            "Force the after-hours (inverted black/white, red preserved) look. "
            "Bypasses the sunset check; intended for layout previews."
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help=(
            "Force the quiet-hours layout (years/months only — hides volatile "
            "metrics that would go stale while the panel is frozen overnight). "
            "Bypasses the sleep_hour check; intended for layout previews."
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=_version_string())
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.preview is None and (args.after_hours or args.quiet):
        log.warning(
            "--after-hours/--quiet are preview flags; forcing them on the live panel"
        )

    cfg = load(args.config or _default_config_path())
    # --now keeps the caller's offset so previews show the exact wall clock.
    if args.now:
        try:
            now = datetime.fromisoformat(args.now)
        except ValueError:
            parser.error(f"--now: not an ISO 8601 datetime: {args.now!r}")
        if now.tzinfo is None:
            parser.error(
                "--now must include a UTC offset, e.g. 2026-04-27T07:47:00-07:00"
            )
    else:
        now = datetime.now(tz=_system_zone())

    # The timer fires hourly all day; the config's wake window decides which
    # hours touch the panel.
    quiet_catchup = False
    # The sleep_hour this catch-up covers: yesterday's, if we're past midnight.
    quiet_catchup_date = None
    if args.preview is None and not (cfg.wake_hour <= now.hour <= cfg.sleep_hour):
        if args.now is None:
            # Pi was off at sleep_hour: paint the quiet layout once so the
            # panel doesn't freeze overnight on volatile metrics.
            from beanclock.display import quiet_refreshed_since
            quiet_catchup_date = (
                now.date()
                if now.hour > cfg.sleep_hour
                else now.date() - timedelta(days=1)
            )
            quiet_catchup = not quiet_refreshed_since(quiet_catchup_date)
        if not quiet_catchup:
            log.info(
                "now=%s hour=%d outside wake window [%d, %d]; skipping refresh",
                now.isoformat(), now.hour, cfg.wake_hour, cfg.sleep_hour,
            )
            return 0
        log.info(
            "missed the sleep_hour=%d refresh; painting quiet catch-up",
            cfg.sleep_hour,
        )

    # The sleep_hour image stays up overnight, so drop volatile metrics.
    quiet = args.quiet or quiet_catchup
    if not quiet and args.now is None:
        quiet = now.hour == cfg.sleep_hour
        if quiet:
            log.info("quiet mode: last refresh before sleep_hour=%d", cfg.sleep_hour)

    after_hours = args.after_hours
    if not after_hours and cfg.after_hours_invert and args.now is None:
        from beanclock.solar import polar_night, sun_times
        # config.load() requires lat/lon when after_hours_invert is set.
        assert cfg.latitude is not None
        assert cfg.longitude is not None
        times = sun_times(now.date(), cfg.latitude, cfg.longitude)
        if times is not None:
            sunrise_local = times[0].astimezone(now.tzinfo)
            sunset_local = times[1].astimezone(now.tzinfo)
            # This image stays up for an hour; go dark if most of it is.
            ahead = now + timedelta(minutes=30)
            after_hours = ahead < sunrise_local or ahead >= sunset_local
            log.info(
                "sunrise=%s sunset=%s after_hours=%s",
                sunrise_local.isoformat(), sunset_local.isoformat(), after_hours,
            )
        else:
            # Sun never crosses the horizon today.
            after_hours = polar_night(now.date(), cfg.latitude, cfg.longitude)
            log.info("no sunrise/sunset today; after_hours=%s", after_hours)

    age = compute(cfg.born_at, now)
    log.info("kid=%s age=%s", cfg.name, age)

    special = detect_special(
        cfg.born_at,
        now,
        age,
        birthday=cfg.birthday,
        milestones=cfg.milestones,
    )
    if special is not None:
        log.info("special-day display: %r", special)

    # Project into now's zone so the footer date matches the age math.
    black, red = render(
        cfg.name,
        age,
        cfg.born_at.astimezone(now.tzinfo),
        accent=cfg.accent,
        flip=cfg.flip,
        age_format=cfg.age_format,
        special=special,
        after_hours=after_hours,
        quiet=quiet,
    )

    if args.preview is not None:
        compose_preview(black, red).save(args.preview)
        log.info("wrote preview to %s", args.preview)
        return 0

    from beanclock.display import record_quiet, show
    show(black, red, today=now.date())
    if quiet and args.now is None:
        # Mark the sleep_hour this refresh covered, not necessarily today's,
        # or a later miss of today's own sleep_hour would be skipped.
        record_quiet(quiet_catchup_date or now.date())
    return 0


if __name__ == "__main__":
    sys.exit(main())

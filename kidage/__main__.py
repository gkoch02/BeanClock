from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from kidage.age import compute
from kidage.config import load
from kidage.render import compose_preview, render
from kidage.special import detect as detect_special

log = logging.getLogger("kidage")


def _default_config_path() -> Path:
    env = os.environ.get("KIDAGE_CONFIG")
    if env:
        return Path(env)
    local = Path("config.toml")
    if local.exists():
        return local
    return Path("/etc/kidage/config.toml")


def _system_zone() -> ZoneInfo:
    # age.compute needs a DST-aware tzinfo to project born_at correctly across
    # DST boundaries. datetime.now().astimezone() yields a fixed-offset
    # datetime.timezone for the *current* moment, which can't replay a winter
    # birth's offset in summer — so resolve the IANA name from the OS instead.
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
    parser = argparse.ArgumentParser(prog="kidage", description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=(
            "Path to TOML config (env: KIDAGE_CONFIG; "
            "default: ./config.toml or /etc/kidage/config.toml)."
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
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    cfg = load(args.config or _default_config_path())
    # The live path needs a DST-aware ZoneInfo (not the fixed-offset tzinfo
    # from `datetime.now().astimezone()`); otherwise age.compute can't project
    # a winter-saved born_at into a summer wall clock and the anniversary
    # slips an hour. --now keeps the caller's offset so layout previews show
    # the exact wall clock requested.
    now = (
        datetime.fromisoformat(args.now)
        if args.now
        else datetime.now(tz=_system_zone())
    )

    # The systemd timer fires hourly all day, so the wake/sleep window in
    # config is what actually decides which hours touch the panel. --preview
    # bypasses the window so layout work doesn't depend on wall-clock time.
    if args.preview is None and not (cfg.wake_hour <= now.hour <= cfg.sleep_hour):
        log.info(
            "now=%s hour=%d outside wake window [%d, %d]; skipping refresh",
            now.isoformat(), now.hour, cfg.wake_hour, cfg.sleep_hour,
        )
        return 0

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

    black, red = render(
        cfg.name,
        age,
        cfg.born_at,
        accent=cfg.accent,
        flip=cfg.flip,
        age_format=cfg.age_format,
        special=special,
    )

    if args.preview is not None:
        compose_preview(black, red).save(args.preview)
        log.info("wrote preview to %s", args.preview)
        return 0

    from kidage.display import show
    show(black, red, today=now.date())
    return 0


if __name__ == "__main__":
    sys.exit(main())

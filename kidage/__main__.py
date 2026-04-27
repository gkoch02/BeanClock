from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from kidage.age import compute
from kidage.config import load
from kidage.render import compose_preview, render

log = logging.getLogger("kidage")


def _default_config_path() -> Path:
    env = os.environ.get("KIDAGE_CONFIG")
    if env:
        return Path(env)
    local = Path("config.toml")
    if local.exists():
        return local
    return Path("/etc/kidage/config.toml")


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
    now = (
        datetime.fromisoformat(args.now)
        if args.now
        else datetime.now(tz=cfg.born_at.tzinfo)
    )
    age = compute(cfg.born_at, now)
    log.info("kid=%s age=%s", cfg.name, age)

    black, red = render(
        cfg.name,
        age,
        cfg.born_at,
        accent=cfg.accent,
        flip=cfg.flip,
        age_format=cfg.age_format,
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

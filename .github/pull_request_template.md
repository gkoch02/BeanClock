## What & why

<!-- One or two sentences: what this changes, and the problem it solves.
     Link the issue if there is one (Fixes #123). -->

## How it was verified

<!-- Delete what doesn't apply; add anything else you ran. -->

- [ ] `pytest` passes
- [ ] `ruff check .` and `mypy` pass
- [ ] Rendered a preview (`python -m kidage --config config.example.toml
      --preview /tmp/p.png`, plus `--now` / `--after-hours` / `--quiet` for
      the affected mode)
- [ ] Exercised on the Pi (`sudo systemctl start kidage.service`,
      `journalctl -u kidage.service`) — needed for `display.py`, the systemd
      units, or `scripts/install.sh`

## Layout changes

<!-- Delete this section if the rendered output is unchanged.
     Otherwise attach before/after previews, and say which accents and
     formats you checked — the frame keep-out and the hero shrink loops make
     clipping easy to miss in one mode. Regenerate docs/preview*.png if the
     README spread is now stale. -->

## Checklist

- [ ] New config knobs are in `config.example.toml`, the dataclass, **and**
      the `_reject_unknown` allow-lists in `kidage/config.py`
- [ ] `vendor/waveshare_epd/` is untouched (fixes belong in
      `kidage/display.py`)
- [ ] `CLAUDE.md` / `README.md` updated if this changes a documented
      invariant or user-facing behavior

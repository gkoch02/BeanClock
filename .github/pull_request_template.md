## What & why

<!-- One or two sentences: what this changes, and the problem it solves.
     Link the issue if there is one (Fixes #123). -->

## How it was verified

<!-- Delete what doesn't apply; add anything else you ran. -->

- [ ] `pytest` passes
- [ ] `ruff check .` and `mypy` pass
- [ ] Rendered a preview (`python -m beanclock --config config.example.toml
      --preview /tmp/p.png`, plus `--now` / `--after-hours` / `--quiet` for
      the affected mode)
- [ ] Exercised on the Pi (`sudo systemctl start beanclock.service`,
      `journalctl -u beanclock.service`) — needed for `display.py`, the systemd
      units, or `scripts/install.sh`

## Layout changes

<!-- Delete this section if the rendered output is unchanged.
     Otherwise attach before/after previews, and say which accents and
     formats you checked — the frame keep-out and the hero shrink loops make
     clipping easy to miss in one mode. Regenerate docs/preview*.png if the
     README spread is now stale. -->

## Checklist

- [ ] New config knobs are in `config.example.toml`, the dataclass, **and**
      the `_reject_unknown` allow-lists in `beanclock/config.py`
- [ ] `vendor/waveshare_epd/` is untouched (fixes belong in
      `beanclock/display.py`)
- [ ] `README.md` updated if user-facing behavior changed
- [ ] `CLAUDE.md` changed only if a rule that spans files was added,
      changed, or removed; rationale lives in the commit message, and code
      comments stay at ~3 lines of non-obvious why

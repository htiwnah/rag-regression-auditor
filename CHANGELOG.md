# Changelog

## v1.0.0 (2026-11-25)
* Upgraded `README.md` to full technical case study format, added five detailed Architecture Decision Records (`ADR-001` through `ADR-005`), and verified all numeric receipts (`76 tests`, `98.61% line coverage`).
* Fixed Python 3.12 CI build failure (`ModuleNotFoundError: No module named 'setuptools'`) by installing `pip setuptools wheel` prior to `--no-build-isolation` in `.github/workflows/ci.yml` and `Dockerfile`.

## v0.4.0 (2026-11-25)
* Added committed SVG hero banner (`docs/banner.svg`), light-background architecture SVG (`docs/architecture.svg`), 1280x640 OpenGraph social preview (`assets/social-preview.png`), terminal screenshots, animated terminal replay GIF (`docs/video/demo.gif`), and interactive GitHub Pages explorer (`docs/index.html`).

## v0.3.0 (2026-11-25)
* Added `tools/collect_metrics.py`, `tools/check_numbers.py`, `tools/check_repo_hygiene.py`, and 3-Python GitHub Actions CI matrix (`.github/workflows/ci.yml`).

## v0.2.0 (2026-11-25)
* Added four deterministic offline experiments (`experiments/run_experiments.py`) measuring `12 false-pass regressions` inside `36 naive passes` at a `2.08% resolution floor`.

## v0.1.0 (2026-11-24)
* Initialized core package, dual-signal lexical/grounded scoring engine, seeded bootstrap CI, CLI exit code contract, SQL schema, and `76 tests`.

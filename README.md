# trajguard

Trajectory privacy attack & protection benchmark. Quantitatively compares privacy
attacks (re-identification, membership inference, reconstruction) across versions of
a trajectory dataset: raw, perturbed, synthetic, and LDP-protected.

Design: `docs/Tehnicna_zasnova_eksperimentalno_okolje.md` ·
Plan: `docs/IMPLEMENTATION_PLAN.md` · Conventions: `CLAUDE.md`

## Development

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync            # create venv and install dev dependencies
uv run ruff check .
uv run mypy src
uv run pytest
```

## Layout

- `src/trajguard/` — package: one subpackage per architecture layer, each exposing
  an abstract interface (`MapSource`, `DatasetLoader`, `MapMatcher`,
  `PrivacyMechanism`, `SyntheticGenerator`, `Attack`, `Metric`); concrete
  implementations register via `trajguard.experiments.registry.register`.
- `data/` — `raw/` is immutable; `interim/`, `processed/`, `protected/`,
  `synthetic/` are regenerable caches (not committed).
- `config/` — YAML experiment configurations.
- `maps/` — built road-network artefacts (not committed).
- `tests/` — unit tests plus a miniature fixture dataset (`tests/fixtures/`).

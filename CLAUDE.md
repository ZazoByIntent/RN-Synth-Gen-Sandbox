# trajguard — Claude Code project guide

Trajectory privacy attack & protection benchmark. Python research codebase for a
doctoral project. This file is the constitution for the repo; read it every session.

**Full design:** `docs/Tehnicna_zasnova_eksperimentalno_okolje.md`.
Read the section relevant to the current task before writing any code.

**Sequenced plan:** `docs/IMPLEMENTATION_PLAN.md`. Work through phases P0→P7 in order.

## Golden rules

- Work in **vertical slices**: get one path running end-to-end before adding breadth.
  Never scaffold a module you are not about to use in the current phase.
- Every new attack / mechanism / dataset / matcher **subclasses the relevant ABC**
  in `src/trajguard/` and registers via `@register(...)`. Never bypass the interfaces.
- `data/raw/` is **immutable** — never write to it. `interim/ processed/ protected/
  synthetic/` are regenerable caches keyed by a version hash.
- **Determinism**: every stochastic step takes an explicit `seed` from config.
  No bare `random` / `np.random` — always a seeded `np.random.Generator`.
- **Map/dataset consistency**: the orchestrator must reject any run where
  `map.region != dataset.native_region`. Geolife/T-Drive → Beijing; Porto → Porto.
  Ljubljana is reserved for synthetic data / RN-LDP-Synth, never for Geolife attacks.
- **RN-LDP-Synth stays a `NotImplementedError` hook** until explicitly told otherwise.
  The benchmark must run on baseline mechanisms without it.

## Conventions

- Python 3.11+, package under `src/trajguard/`. Env with `uv`, lint/format with
  `ruff`, types with `mypy`, tests with `pytest`.
- Data on disk as **Parquet**; query with **DuckDB**. No PostGIS in the MVP.
- Public functions get type hints and a one-line docstring. No dead scaffolding,
  no speculative abstraction beyond the five ABCs.
- Commits small and scoped. One phase = one branch = one PR.

## Definition of done (applies to every task)

1. `ruff check` and `mypy` are clean.
2. A test exists and passes against the `tests/` fixture (~20 trajectories);
   the whole suite runs in seconds.
3. You **show the evidence**: paste the exact command you ran and its output.
   Do not assert "it works" — prove it with the test output or a small run.

## How to work in this repo

- Start any non-trivial task in **plan mode**. Show the plan, wait for my approval
  before editing files.
- Use a **subagent** for research-heavy reading (e.g. how a library expects input),
  so the main context stays clean.
- If a task would touch more than ~5 files or mixes concerns, **stop and propose a
  split** instead of doing it all at once.
- Prefer editing existing files over creating new ones unless the design calls for a
  new module.

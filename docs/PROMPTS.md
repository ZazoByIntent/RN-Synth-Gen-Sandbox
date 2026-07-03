# Prompti za implementacijo — trajguard

Pripravljeni prompti za Claude Code, en na fazo iz `docs/IMPLEMENTATION_PLAN.md`.
Uporaba: odpri Claude Code v korenu repozitorija in **prilepi prompt za trenutno fazo**.
Vsak prompt sledi vzorcu Research → Plan → Execute → Review, ki ga vgrajuje CLAUDE.md.

Splošno pravilo: **eno fazo naenkrat, ena veja, en PR.** Ne prilepi več faz skupaj.

---

## Enkratni uvodni prompt (pred P0)

```
Read CLAUDE.md and docs/IMPLEMENTATION_PLAN.md in full, and skim
docs/Tehnicna_zasnova_eksperimentalno_okolje.md so you have the architecture in mind.
Do not write any code yet. When done, summarise back to me in 5 bullet points:
(1) the vertical-slice principle, (2) the five ABCs and where they live,
(3) the map/dataset consistency rule, (4) the definition of done, (5) how phases map
to branches/PRs. Then wait.
```

---

## P0 — Bootstrap

```
We're doing phase P0 from docs/IMPLEMENTATION_PLAN.md. Start in plan mode.

Goal: repo scaffolding, tooling, the datamodel schemas, the registry, and the seven
ABCs (MapSource, DatasetLoader, MapMatcher, PrivacyMechanism, SyntheticGenerator,
Attack, Metric) as defined in section 2.3 and section 4 of the design doc. No domain
logic yet — the ABCs have abstract methods and docstrings only.

Constraints from CLAUDE.md apply: Python 3.11+, uv, ruff, mypy, pytest, src layout.
Add a GitHub Actions workflow running ruff + mypy + pytest. Create the tests/ fixture
folder empty for now, plus tests/test_registry.py.

Show me the plan and the proposed file tree before writing anything. After I approve,
implement, then run ruff + mypy + pytest and paste the output as evidence.
```

---

## P1 — Mapa in zbirka

```
Phase P1 from the implementation plan. Start in plan mode.

Implement OSMMapSource (OSMnx, project to EPSG:32650, save GraphML + edges/nodes
Parquet) and GeolifeLoader (parse .plt, native_region="beijing", yield RawTrajectory),
plus cleaning.py (speed filter, min length, min points, resampling → CleanTrajectory).

Before coding, use a subagent to check how OSMnx returns the graph and how Geolife
.plt files are structured, and report back — keep that research out of the main context.

Build a small test fixture: ~20 truncated Geolife trajectories and a tiny slice of the
Beijing network, committed under tests/fixtures/. Add tests/test_geolife.py and
tests/test_cleaning.py. DoD: cleaning removes known outliers on the fixture; the
network loads and saves. Show test output.
```

---

## P2 — Map matching

```
Phase P2. Start in plan mode.

Implement LeuvenMapMatcher(MapMatcher) using leuvenmapmatching (we pick this over fmm
for now because it's easier to debug during calibration; keep the MapMatcher interface
clean so fmm can slot in later). Compute match quality: mean GPS-to-road distance,
fraction of matched points, and drop trajectories below min_match_score.

Also create notebooks/01_matching_sanity.ipynb that visualises 5–10 matched
trajectories over the network so I can eyeball correctness before we trust it at scale.

Add tests/test_matching.py on the fixture network. DoD: a known fixture trajectory
produces the expected edge sequence. Show test output.
```

---

## P3 — Delitev, pogledi, baseline

```
Phase P3. Start in plan mode.

Implement: (1) split.py — by_user split into train/test/shadow/attack, stratified,
fixed seed, no user overlap between train and attack, split label propagated forward;
(2) representation/views.py — TrajectoryView with as_gps(), as_segments(),
as_cells(grid); leave POI and graph views as NotImplementedError for now;
(3) privacy/none.py — NoProtection(PrivacyMechanism), guarantee="none".

Add tests/test_split.py (determinism: same seed → same split) and tests/test_views.py.
Show test output.
```

---

## P4 — Prvi napad + orkestrator + prvi run

```
Phase P4 — this closes the vertical slice. Start in plan mode.

Implement: (1) ReidentificationAttack(Attack) — attacker knows k points of the target,
nearest-neighbour over matched trajectories using DTW; target_scope {raw, protected};
(2) evaluation/metrics.py — TopKAccuracy, LinkageRate, with bootstrap confidence
intervals; (3) experiments/orchestrator.py — reads YAML, REJECTS runs where
map.region != dataset.native_region, sets seeds, runs the pipeline, caches artefacts by
a version hash; (4) config/experiments/geolife_reid_baseline.yaml per section 8 of the
design doc (no protection).

Add tests for the attack and the orchestrator, including a test that the consistency
check rejects a Ljubljana+Geolife config.

DoD: `trajguard run config/experiments/geolife_reid_baseline.yaml` runs end-to-end from
raw Geolife to top-k accuracy with bootstrap CI, writing to results/. Run it and paste
the actual output as evidence.
```

---

## P5 — Zaščita + ponovni napad

```
Phase P5. Start in plan mode.

Implement GeoIndistinguishability(PrivacyMechanism) — planar Laplace, guarantee
"geo-ind", epsilon parameter, spent_budget(). Extend the orchestrator to expand a
parameter grid (epsilon [0.1, 1, 10] × known_points). Add utility metrics
CellJSDivergence and LengthDistError. Add config/experiments/geolife_geoind_reid.yaml.

DoD: a results matrix (epsilon × known_points) comparing reidentification on raw vs
protected, plus one privacy-vs-utility tradeoff curve. Tests for the mechanism. Show
the run output and the generated matrix.
```

---

## P6 — Sinteza + MIA + rekonstrukcija

```
Phase P6. Start in plan mode. This is three related pieces — if it gets too large,
propose splitting into P6a/P6b/P6c.

Implement: (1) MarkovGenerator(SyntheticGenerator) — n-gram over segment sequences,
strictly separating train/test/synthetic; (2) MembershipInferenceAttack — LiRA-lite
with shadow generators and a likelihood-ratio score, reporting TPR at FPR in
{0.001, 0.01} and AUC, target_scope {synthetic}; (3) ReconstructionAttack — MAP
inversion of the known mechanism, reporting Hausdorff, DTW, mean spatial error,
target_scope {protected}.

Each attack gets a test checking it behaves sensibly on the fixture. Show test output.
```

---

## P7 — Poročanje

```
Phase P7. Start in plan mode.

Implement reporting/: export_tables() (CSV/Parquet), risk_matrix() (attack × mechanism
× parameters), plot_tradeoff(), summarize_by_attack(), and a Jinja2 report template
rendering to reports/.

DoD: one command generates the risk matrix, tradeoff plots, and a Markdown summary from
whatever is in results/. This is the building block for the IZV risk report. Show me
the generated report on the current results.
```

---

## Ponovljivi review prompt (po vsaki fazi, pred merge)

```
Review the diff for this phase as a fresh reviewer. Check against CLAUDE.md: are the
interfaces respected, is determinism handled (explicit seeds), is data/raw untouched,
are there tests that actually run, and is the map/dataset consistency rule intact?
List any violations with file and line. Don't fix anything yet — just report.
```

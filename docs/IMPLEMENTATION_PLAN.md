# Implementacijski načrt — trajguard

Fazni načrt za implementacijo z Claude Code. Vsaka faza je zaključena, preverljiva
enota z jasno definicijo dokončanosti (DoD). Faze P0–P4 sestavljajo **vertikalno
rezino** (od surovih podatkov do prvega rezultata z intervali zaupanja); P5–P7 dodajo
širino. Za vsako fazo obstaja pripravljen prompt v `docs/PROMPTS.md`.

Načelo: **ne nadaljuj na naslednjo fazo, dokler DoD trenutne ni izpolnjen.** Cilj ni
hitro imeti veliko kode, ampak imeti vsak korak preverjen s testom.

Poravnava s sprinti IZV: P0 ≈ S0, P1 ≈ S1, P2–P4 ≈ S2, P5–P6 ≈ S3, P7 ≈ S5.

---

## P0 — Bootstrap in ogrodje

**Cilj:** postaviti strukturo, orodja in pet abstraktnih vmesnikov + register. Nič
domenske logike še.

**Nastane:**
- `pyproject.toml` (uv, ruff, mypy, pytest), `.gitignore`, `README.md`.
- Struktura map iz zasnove (§9): `src/trajguard/{maps,datasets,matching,representation,privacy,synthesis,attacks,evaluation,experiments,reporting,datamodel}/`, `data/`, `maps/`, `config/`, `tests/`.
- `src/trajguard/datamodel/` — dataclass/pydantic sheme entitet iz zasnove (§4): `Map`, `CleanTrajectory`, `MatchedTrajectory`, `ProtectedTrajectory`, `SyntheticTrajectory`, `AttackResult`, `MetricValue`, `ExperimentConfig`.
- `src/trajguard/experiments/registry.py` — `register(kind, name)` dekorator + `get(kind, name)` lookup.
- Pet ABC iz zasnove (§2.3): `MapSource`, `DatasetLoader`, `MapMatcher`, `PrivacyMechanism`, `SyntheticGenerator`, `Attack`, `Metric` (vsak v svojem modulu).
- `tests/test_registry.py`, `tests/conftest.py` (prazna fixture za zdaj).
- GitHub Actions CI stub: ruff + mypy + pytest.

**DoD:** `ruff check`, `mypy src`, `pytest` — vse zeleno. `register`/`get` ima test.
Uvoz `import trajguard` deluje. CI teče.

---

## P1 — Mapa in zbirka (Beijing + Geolife)

**Cilj:** naložiti cestno omrežje Beijinga in uvoziti + očistiti vzorec Geolife.

**Nastane:**
- `src/trajguard/maps/osm.py` — `OSMMapSource(MapSource)` prek OSMnx; download po bbox, projekcija v EPSG:32650, shranjevanje grafa (GraphML) + povezav/vozlišč (Parquet), `load()`.
- `src/trajguard/datasets/geolife.py` — `GeolifeLoader(DatasetLoader)`; parsira `.plt`, `native_region="beijing"`, vrne `RawTrajectory`.
- `src/trajguard/datasets/cleaning.py` — hitrostni filter, min. dolžina, min. št. točk, resampling; vrne `CleanTrajectory`.
- Mala testna fixture: 20 skrajšanih poti + drobec omrežja v `tests/fixtures/`.
- `tests/test_geolife.py`, `tests/test_cleaning.py`.

**DoD:** iz vzorca Geolife dobiš `CleanTrajectory` zapise; test preveri, da čiščenje
odstrani znane outlierje na fixture. Omrežje Beijing se naloži in shrani.

---

## P2 — Map matching

**Cilj:** preslikati očiščene GPS poti na cestne segmente + oceniti kakovost.

**Nastane:**
- `src/trajguard/matching/leuven.py` — `LeuvenMapMatcher(MapMatcher)` (za kalibracijo; lažje debugiranje). Vmesnik pusti odprt za `fmm` kasneje.
- Izračun kakovosti: povprečna GPS→cesta razdalja, delež ujetih točk, filter po `min_match_score`.
- Notebook `notebooks/01_matching_sanity.ipynb` — vizualni pregled 5–10 poti (glej priporočilo §13.3).
- `tests/test_matching.py` (na fixture omrežju).

**DoD:** `MatchedTrajectory` z `edge_seq` in `match_score`; poti pod pragom se
zavržejo; test na fixture preveri, da znana pot dobi pričakovano zaporedje segmentov.

---

## P3 — Delitev, pogledi, baseline brez zaščite

**Cilj:** enkratna delitev množic + pogledi trajektorij + `NoProtection`.

**Nastane:**
- `src/trajguard/datasets/split.py` — delitev `by_user` na train/test/shadow/attack, stratificirano, s fiksnim seedom; oznaka `split` se propagira naprej.
- `src/trajguard/representation/views.py` — `TrajectoryView` z `as_gps()`, `as_segments()`, `as_cells(grid)` (POI in graph pogled lahko za zdaj `NotImplementedError`).
- `src/trajguard/privacy/none.py` — `NoProtection(PrivacyMechanism)`, `guarantee="none"`.
- `tests/test_split.py`, `tests/test_views.py`.

**DoD:** delitev je deterministična (isti seed → ista razdelitev), brez prekrivanja
uporabnikov med train in attack. Pogledi vračajo pričakovane oblike na fixture.

---

## P4 — Prvi napad + vrednotenje + prvi end-to-end run

**Cilj:** reidentifikacija na nezaščitenih podatkih, metrike, cel cevovod iz YAML.

**Nastane:**
- `src/trajguard/attacks/reidentification.py` — `ReidentificationAttack(Attack)`; napadalec pozna k točk tarče; NN v prostoru značilk (DTW/Hausdorff nad matched potmi); `target_scope={"raw","protected"}`.
- `src/trajguard/evaluation/metrics.py` — `TopKAccuracy`, `LinkageRate`; bootstrap CI (§13).
- `src/trajguard/experiments/orchestrator.py` — bere YAML, validira skladnost mape/zbirke, nastavi seede, izvede run graph, cache po verzijskem ključu.
- `config/experiments/geolife_reid_baseline.yaml` (iz zasnove §8, brez zaščite).
- `tests/test_reidentification.py`, `tests/test_orchestrator.py`.

**DoD:** en ukaz (`trajguard run config/experiments/geolife_reid_baseline.yaml`)
požene celoten cevovod od surovega Geolife do top-k natančnosti z bootstrap CI.
Rezultat se zapiše v `results/`. To je konec vertikalne rezine.

---

## P5 — Zaščita + ponovni napad + trade-off

**Cilj:** dodati perturbacijo in izvesti isti napad na zaščitenih podatkih.

**Nastane:**
- `src/trajguard/privacy/geoind.py` — `GeoIndistinguishability(PrivacyMechanism)` (planar Laplace), `guarantee="geo-ind"`, `epsilon` parameter, `spent_budget()`.
- Podpora za mreže parametrov v orkestratorju (`epsilon: [0.1, 1, 10] × known_points`).
- Uporabnostne metrike: `CellJSDivergence`, `LengthDistError`.
- `config/experiments/geolife_geoind_reid.yaml`.

**DoD:** matrika rezultatov *(ε × known_points)* za reidentifikacijo na raw vs
protected, plus ena trade-off krivulja (zasebnost vs uporabnost). Testi za mehanizem.

---

## P6 — Sinteza + MIA + rekonstrukcija

**Cilj:** preprost generator, napad na članstvo, rekonstrukcijski napad.

**Nastane:**
- `src/trajguard/synthesis/markov.py` — `MarkovGenerator(SyntheticGenerator)` (n-gram nad segmenti); strogo loči train/test/synthetic.
- `src/trajguard/attacks/membership.py` — `MembershipInferenceAttack(Attack)` v slogu LiRA-lite (senčni generatorji, likelihood-ratio); metrika TPR@nizek FPR + AUC. `target_scope={"synthetic"}`.
- `src/trajguard/attacks/reconstruction.py` — `ReconstructionAttack(Attack)`; MAP inverzija znanega mehanizma; metrike Hausdorff, DTW, povprečna prostorska napaka. `target_scope={"protected"}`.
- Ustrezni testi.

**DoD:** MIA poroča TPR pri FPR ∈ {0.001, 0.01} in AUC; rekonstrukcija poroča
prostorsko napako. Vsak napad ima test, ki preveri smiselnost na fixture.

---

## P7 — Poročanje

**Cilj:** matrika tveganj, grafi, Markdown poročilo.

**Nastane:**
- `src/trajguard/reporting/` — `export_tables()` (CSV/Parquet), `risk_matrix()` (napad × mehanizem × parametri), `plot_tradeoff()`, `summarize_by_attack()`.
- Predloga poročila (Jinja2) → `reports/`.

**DoD:** en ukaz zgenerira matriko tveganj + trade-off grafe + Markdown povzetek iz
rezultatov v `results/`. To je gradnik za 20-stransko poročilo IZV.

---

## Kaj namerno NI v tem načrtu (horizont B, 2. letnik)

Federativni pristopi, k-anonimnost, diffusion generatorji (Diff-RNTraj/ControlTraj),
attribute inference, T-Drive/Porto, PostGIS, MLflow tracking, RN-LDP-Synth kot
dejanska implementacija. Vse to se priključi prek obstoječih vmesnikov brez sprememb
jedra, ko bo vertikalna rezina delovala.

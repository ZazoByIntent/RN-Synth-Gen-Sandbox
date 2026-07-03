# Tehnična zasnova: Eksperimentalno okolje za analizo zasebnostnih tveganj lokacijskih podatkov

**Delovno ime:** `trajguard` (Trajectory Privacy Attack & Protection Benchmark)
**Avtor:** Aljaž Hafner
**Kontekst:** predmeta IZV (*Informacijska zasebnost in varnost*) in NPZ (*Napredna podatkovna zaščita*); dolgoročno benchmarking okolje za disertacijo RN-LDP-Synth
**Verzija dokumenta:** 1.0 (Sprint 0/1, julij 2026)

---

## 0. Umestitev in obseg (preberi najprej)

Ta zasnova pokriva **dva različna horizonta**, ki ju je treba jasno ločiti:

| Horizont | Predmet | Kaj se dejansko implementira | Kdaj |
| --- | --- | --- | --- |
| **A – MVP** | IZV (S1–S5) | Ena mapa + Geolife, čiščenje, map-matching, en baseline brez zaščite, ena perturbacija, en preprost generator, 3 napadi, osnovne metrike | zdaj (jul–avg 2026) |
| **B – polno okolje** | Kosarjev eksp. predmet | Modularen benchmark z vsemi mehanizmi, generatorji in napadi; orkestracija prek konfiguracij | 2. letnik |

Arhitektura spodaj je zasnovana za horizont B (da kasneje ne prepisuješ), a je **razrezana tako, da je MVP izvedljiv v nekaj sprintih brez gradnje celotnega ogrodja**. Vsak modul ima jasno definiran vmesnik; v MVP-ju implementiraš po eno konkretno izvedbo na vmesnik.

### Kritična predpostavka: konsistentnost mape in zbirke

Geolife in T-Drive sta zbirki iz **Pekinga**, Porto Taxi iz **Porta**. Map-matching in vsi omrežno-odvisni napadi zahtevajo, da je cestno omrežje geografsko skladno z zbirko. Zato:

- `Geolife` in `T-Drive` → **OSM Beijing** (CRS EPSG:32650, UTM 50N)
- `Porto Taxi` → **OSM Porto** (CRS EPSG:32629, UTM 29N)
- `OSM Ljubljana` (CRS EPSG:3794, D96/TM) → **sintetične poti in RN-LDP-Synth**, ne za Geolife

Mapa in zbirka sta v podatkovnem modelu vezani prek eksplicitnega para `(map_id, dataset_id)`; orkestrator zavrne konfiguracijo, kjer se koordinatna sistema ne ujemata (glej §12, Tveganje T3).

---

## 1. Kratek povzetek cilja okolja

Okolje omogoča **kvantitativno primerjavo uspešnosti napadov na zasebnost** med različnimi verzijami iste zbirke poti: (1) nezaščiteni izvorni podatki, (2) perturbirani/zašumljeni, (3) sintetično generirani, (4) anonimizirani z LDP ali drugimi mehanizmi. Osrednji rezultat je **matrika tveganj** oblike *(napad × zaščitni mehanizem × parametri)* z merami zasebnosti in uporabnosti, ki podpre trditev, kdaj in kako anonimizacija dejansko ščiti posameznika. Okolje je **modularno** (nove mape, zbirke, mehanizmi, napadi se dodajajo prek vmesnikov), **ponovljivo** (vse iz YAML konfiguracij + fiksni seedi + verzioniranje podatkov) in **razširljivo** (od enega baseline napada do celotne serije simulacij).

---

## 2. Arhitektura sistema

### 2.1 Pregled slojev

```
┌──────────────────────────────────────────────────────────────────────┐
│  Experiment Orchestrator  (YAML/JSON → run graph, seedi, verzije)      │
└───────────────┬──────────────────────────────────────────────────────┘
                │ vodi izvajanje
   ┌────────────┼──────────────────────────────────────────────────┐
   ▼            ▼               ▼                ▼                    ▼
┌────────┐ ┌──────────┐ ┌─────────────┐ ┌───────────────┐ ┌───────────────┐
│  Map   │ │ Dataset  │ │ Map Matching│ │ Privacy Mech. │ │ Synthetic Gen.│
│Manager │ │ Manager  │ │  Pipeline   │ │    Layer      │ │    Layer      │
└───┬────┘ └────┬─────┘ └──────┬──────┘ └───────┬───────┘ └───────┬───────┘
    │           │              │                │                 │
    └───────────┴──────┬───────┴────────────────┴─────────────────┘
                       ▼
              ┌─────────────────────┐
              │ Trajectory Repr.    │  (GPS / segmenti / celice / graf / POI)
              │      Layer          │
              └─────────┬───────────┘
                        ▼
              ┌─────────────────────┐        ┌─────────────────────┐
              │    Attack Engine    │───────▶│  Evaluation Engine  │
              │ (reid/MIA/rec/attr) │        │ (metrike, CI, testi)│
              └─────────────────────┘        └──────────┬──────────┘
                                                        ▼
                                             ┌─────────────────────┐
                                             │ Results & Reporting  │
                                             └─────────────────────┘

    Prečno:  Data Store (Parquet/DuckDB)  +  Experiment Tracking (MLflow)
```

### 2.2 Moduli

Za vsak modul: **namen / vhod / izhod / glavne funkcije / tehnologije**. Ključna oblika razširljivosti (`◆ vmesnik`) je označena.

#### 1. Map Manager `◆ MapSource`
- **Namen:** priprava cestnega grafa iz OSM (ali sintetičnega vira), rezanje območja, shranjevanje.
- **Vhod:** ime območja / bounding box / OSM `.pbf`; ciljni CRS.
- **Izhod:** `RoadNetwork` (NetworkX MultiDiGraph + GeoDataFrame vozlišč/povezav), shranjen kot GraphML + GeoPackage/Parquet.
- **Funkcije:** `download(area)`, `clip(bbox)`, `build_graph()`, `project(crs)`, `save()/load()`, indeks povezav (R-tree) za map-matching.
- **Tehnologije:** OSMnx, NetworkX, GeoPandas, Shapely, `rtree`/`pyproj`.

#### 2. Dataset Manager `◆ DatasetLoader`
- **Namen:** enoten uvoz heterogenih zbirk, čiščenje, filtriranje, delitev na množice.
- **Vhod:** surove datoteke (Geolife `.plt`, T-Drive CSV, Porto `POLYLINE`).
- **Izhod:** `RawTrajectory` / `CleanTrajectory` zapisi (Parquet), splitting metadata.
- **Funkcije:** `iter_trajectories()`, `clean(cfg)`, `filter(bbox|user|time|min_len)`, `split(train/test/shadow/attack)`.
- **Tehnologije:** Pandas/PyArrow, GeoPandas.

#### 3. Map Matching Pipeline `◆ MapMatcher`
- **Namen:** preslikava GPS točk na cestne segmente, obravnava šuma in vrzeli, ocena kakovosti.
- **Vhod:** `CleanTrajectory` + `RoadNetwork`.
- **Izhod:** `MatchedTrajectory` (zaporedje `edge_id`, projicirane točke, offset, match score).
- **Funkcije:** `match(traj, network)`, `quality(matched)` (povprečna GPS→cesta razdalja, delež ujetih točk, delež nesmiselnih hitrosti).
- **Tehnologije:** `fmm` (Fast Map Matching, C++/HMM, hitro, potrebuje UBODT) ali `leuvenmapmatching` (čisti Python, lažje debugiranje). Referenca: Newson & Krumm 2009 (HMM/Viterbi).

#### 4. Trajectory Representation Layer `◆ TrajectoryView`
- **Namen:** enoten dostop do različnih pogledov iste poti (adapter vzorec).
- **Vhod:** `MatchedTrajectory` / `CleanTrajectory`.
- **Izhod:** en od pogledov: GPS-sekvenca, sekvenca `edge_id`, prostorsko-časovne celice (grid/geohash), grafovska pot, sekvenca POI-obiskov.
- **Funkcije:** `as_gps()`, `as_segments()`, `as_cells(grid)`, `as_graph_path()`, `as_poi_visits(poi_layer)`.
- **Tehnologije:** NumPy, Shapely, `h3`/geohash, NetworkX.

#### 5. Privacy Mechanism Layer `◆ PrivacyMechanism`
- **Namen:** enoten vmesnik za zaščitne transformacije + beleženje privacy budgeta.
- **Vhod:** trajektorija (ustrezen pogled) + parametri (npr. ε).
- **Izhod:** zaščitena trajektorija + `PrivacyReport` (porabljen ε, tip garancije).
- **Funkcije:** `apply(traj, params)`, `budget()`, `guarantee_type()` (central-DP / LDP / geo-ind / k-anon / brez).
- **Tehnologije:** NumPy, SciPy; za LDP lastne implementacije mehanizmov.

#### 6. Synthetic Data Generator Layer `◆ SyntheticGenerator`
- **Namen:** učenje generativnega modela na train množici in generiranje sintetičnih poti.
- **Vhod:** train množica poti (v ustreznem pogledu).
- **Izhod:** sintetične poti + metapodatki o učni množici (za MIA).
- **Funkcije:** `fit(train)`, `generate(n)`, `save()/load()`. **Strogo loči** train/test/synthetic (za pošten MIA).
- **Tehnologije:** PyTorch (za diffusion, npr. Diff-RNTraj/ControlTraj), preprosti baseline: Markov/n-gram na segmentih, DP-histogram (DPT-lite).

#### 7. Attack Engine `◆ Attack`
- **Namen:** enoten vmesnik za napade z nastavljivim predznanjem napadalca.
- **Vhod:** ciljni podatki (izvorni/zaščiteni/sintetični) + pomožno znanje (`BackgroundKnowledge`).
- **Izhod:** `AttackResult` (napovedi, scores, ground-truth povezave).
- **Funkcije:** `configure(knowledge)`, `run(target, aux)`, `attacker_model()`.
- **Tehnologije:** scikit-learn, NumPy; za senčne modele PyTorch.

#### 8. Evaluation Engine
- **Namen:** izračun metrik, primerjava mehanizmov, trade-off, statistika, vizualizacija.
- **Vhod:** `AttackResult` + ground truth + `UtilityInput`.
- **Izhod:** `MetricSet`, bootstrap CI, rezultati testov, grafi.
- **Funkcije:** `privacy_metrics()`, `utility_metrics()`, `tradeoff()`, `bootstrap_ci()`, `significance_test()`.
- **Tehnologije:** NumPy/SciPy, scikit-learn (AUC/ROC), Matplotlib, Pandas.

#### 9. Experiment Orchestrator
- **Namen:** izvedba eksperimenta iz konfiguracije, ponovljivost.
- **Vhod:** YAML/JSON konfiguracija.
- **Izhod:** izveden run graph, logi, verzionirani artefakti.
- **Funkcije:** `run(config)`, `set_seed()`, `version(data)`, `track()`, validacija konsistentnosti mape/zbirke.
- **Tehnologije:** Hydra ali OmegaConf (konfiguracije), MLflow (tracking), Snakemake/lasten DAG (odvisnosti korakov).

#### 10. Results & Reporting Layer
- **Namen:** izvoz rezultatov, tabel, grafov, povzetkov po napadih.
- **Vhod:** `MetricSet`, matrika tveganj.
- **Izhod:** CSV/Parquet, PNG/SVG grafi, Markdown/LaTeX tabele za poročilo.
- **Funkcije:** `export_tables()`, `plot_tradeoff()`, `summarize_by_attack()`, `comparison_matrix()`.
- **Tehnologije:** Pandas, Matplotlib/Plotly, Jinja2 (poročilo).

### 2.3 Kaj naj bo vmesnik / abstraktni razred

Pet ključnih razširitvenih točk (vse `abc.ABC`), da lahko dodajaš brez posega v jedro:

```python
from abc import ABC, abstractmethod
from typing import Iterator, Sequence

class MapSource(ABC):
    @abstractmethod
    def load(self) -> "RoadNetwork": ...
    @property
    @abstractmethod
    def crs(self) -> str: ...

class DatasetLoader(ABC):
    dataset_id: str
    native_region: str          # npr. "beijing" — za validacijo skladnosti
    @abstractmethod
    def iter_trajectories(self) -> Iterator["RawTrajectory"]: ...

class MapMatcher(ABC):
    @abstractmethod
    def match(self, traj: "CleanTrajectory", net: "RoadNetwork") -> "MatchedTrajectory": ...

class PrivacyMechanism(ABC):
    guarantee: str              # "none" | "geo-ind" | "ldp" | "central-dp" | "k-anon"
    @abstractmethod
    def apply(self, traj: "TrajectoryView", **params) -> "ProtectedTrajectory": ...
    @abstractmethod
    def spent_budget(self) -> float | None: ...

class SyntheticGenerator(ABC):
    @abstractmethod
    def fit(self, train: Sequence["TrajectoryView"]) -> None: ...
    @abstractmethod
    def generate(self, n: int, seed: int) -> Sequence["SyntheticTrajectory"]: ...

class Attack(ABC):
    target_scope: set[str]      # {"raw","protected","synthetic"} — kje je napad smiseln
    @abstractmethod
    def configure(self, knowledge: "BackgroundKnowledge") -> None: ...
    @abstractmethod
    def run(self, target, aux) -> "AttackResult": ...

class Metric(ABC):
    @abstractmethod
    def compute(self, result: "AttackResult", ground_truth) -> dict: ...
```

Vse konkretne izvedbe se registrirajo prek registra (`ptregistry`), tako da jih orkestrator naslavlja po imenu iz konfiguracije:

```python
@register("attack", "reidentification")
class ReidentificationAttack(Attack): ...
```

---

## 3. Podatkovni tok

```
surove datoteke ──► [Dataset Manager] ──► RawTrajectory (parquet, data/raw)
                                              │
                                     clean(cfg)│
                                              ▼
OSM area ──► [Map Manager] ──► RoadNetwork    CleanTrajectory (data/interim)
                     │                        │
                     └──────────┬─────────────┘
                                ▼
                        [Map Matching]
                                │
                                ▼
                     MatchedTrajectory (data/processed)
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
     [Privacy Mechanism]   [Synthetic Gen.]   (nezaščiten baseline)
              │                 │                 │
    ProtectedTrajectory  SyntheticTrajectory   MatchedTrajectory
              │                 │                 │
              └─────────────────┼─────────────────┘
                                ▼
                        [Trajectory Views]
                                ▼
                          [Attack Engine] ──► AttackResult
                                ▼
                       [Evaluation Engine] ──► MetricSet
                                ▼
                     [Results & Reporting] ──► CSV/Parquet, grafi, tabele
```

Vsak prehod zapiše artefakt z **verzijskim ključem** (`hash(config + input_hash + seed)`), tako da je vsaka izvedena verzija zbirke enolično identificirana in ponovljiva. Delitev na `train/test/shadow/attack` se izvede **enkrat na ravni CleanTrajectory** in se dosledno propagira naprej, da MIA ostane pošten.

---

## 4. Podatkovni model

Za vsak objekt ključna polja. Shramba: Parquet po tabelah (`DuckDB` kot poizvedbeni sloj), ID-ji so stabilni med koraki.

**Map**
`map_id`, `source` (osm/synthetic), `region`, `bbox`, `crs`, `osm_timestamp`, `path_graph`, `path_edges`, `path_nodes`.

**RoadGraph (vozlišča/povezave)**
- vozlišče: `node_id`, `x`, `y`, `lon`, `lat`, `street_count`.
- povezava: `edge_id`, `u`, `v`, `key`, `geometry`, `length_m`, `highway`, `oneway`, `maxspeed`.

**User**
`user_id`, `dataset_id`, `n_trajectories`, `region`, (opcijsko demografski atributi za attribute inference, če obstajajo).

**RawTrajectory**
`traj_id`, `user_id`, `dataset_id`, `points`[(lat, lon, t, alt?)], `start_t`, `end_t`, `n_points`, `source_file`.

**CleanTrajectory**
`traj_id`, `user_id`, `points`[(lat, lon, t)], `bbox`, `duration_s`, `length_m`, `mean_speed`, `cleaning_flags`, `split` ∈ {train, test, shadow, attack}.

**MatchedTrajectory**
`traj_id`, `user_id`, `map_id`, `edge_seq`[edge_id], `matched_points`[(x, y, t, offset_m)], `match_score`, `frac_matched`.

**ProtectedTrajectory**
`traj_id`, `source_traj_id`, `mechanism_id`, `params_hash`, `guarantee`, `epsilon`, `payload` (odvisno od pogleda), `map_id`.

**SyntheticTrajectory**
`syn_id`, `generator_id`, `params_hash`, `payload`, `trained_on_split` (referenca train množice), `map_id`.

**Experiment**
`exp_id`, `config_hash`, `map_id`, `dataset_id`, `git_commit`, `seed`, `created_at`, `mlflow_run_id`.

**Attack**
`attack_id`, `attack_type`, `attacker_model`, `background_knowledge` (JSON), `target_data_ref`, `params_hash`.

**AttackResult**
`result_id`, `attack_id`, `exp_id`, `target_data_ref`, `predictions`, `scores`, `ground_truth_ref`, `runtime_s`.

**Metric**
`metric_id`, `result_id`, `name`, `value`, `ci_low`, `ci_high`, `n_bootstrap`.

**Config**
`config_hash`, `raw_yaml`, `resolved_yaml`, `schema_version`.

Relacijsko: `Experiment 1─* Attack 1─* AttackResult 1─* Metric`; `ProtectedTrajectory.source_traj_id → MatchedTrajectory.traj_id`.

---

## 5. Eksperimentalni protokol

1. **Izbira mape** – naloži/zgradi `RoadNetwork` za območje, skladno z zbirko.
2. **Uvoz zbirke** – `DatasetLoader.iter_trajectories()`.
3. **Čiščenje** – odstrani outlierje (hitrost > prag), filtriraj po bbox/uporabniku/min. dolžini, resampliraj.
4. **Map matching** – `MatchedTrajectory` + poročilo kakovosti; odstrani poti pod pragom kakovosti.
5. **Delitev** – `train/test/shadow/attack` (enkrat, stratificirano po uporabniku, fiksni seed).
6. **Baseline napadi** – izvedi izbrane napade na **nezaščitenih** podatkih (referenčna zgornja meja tveganja).
7. **Zaščita** – uporabi izbrane `PrivacyMechanism` z mrežo parametrov (npr. ε ∈ {0.1, 1, 10}).
8. **Napadi na zaščitenih** – isti napadi, iste konfiguracije napadalca.
9. **Sinteza** – kjer je relevantno, `SyntheticGenerator.fit(train).generate(n)`.
10. **MIA na sintetičnih** – LiRA-slog (Carlini 2022): senčni modeli, likelihood-ratio; poročaj TPR@nizek FPR.
11. **Metrike zasebnosti** – po napadu (glej §6).
12. **Metrike uporabnosti** – npr. ohranjenost porazdelitve dolžin, obisk celic, OD-matrike, hitrostni profili.
13. **Trade-off** – zasebnost vs. uporabnost pri istem ε; Pareto fronta.
14. **Vizualizacija** – ROC/TPR@FPR, tradeoff krivulje, toplotne matrike tveganj.
15. **Zaključki** – kateri mehanizem ščiti proti kateremu napadu in za kakšno ceno uporabnosti.

Vsak korak je idempotenten in cache-an po verzijskem ključu; ponovni zagon preskoči že izračunane artefakte.

---

## 6. Napadi in metrike

Neposredno vezano na tvojo taksonomijo iz načrta IZV. Za vsak napad: cilj, predznanje, obseg (kje je smiseln), metrike.

### 6.1 Reidentifikacija / linkage (de Montjoye 2013)
- **Cilj:** povezati objavljeno/zaščiteno pot z znanim posameznikom.
- **Predznanje:** delna ali cela pot tarče (k prostorsko-časovnih točk).
- **Obseg:** `raw`, `protected`.
- **Pristop:** nearest-neighbour v prostoru značilk (npr. Hausdorff/DTW nad matched poti), ali unikatnost k točk (spatio-temporal uniqueness).
- **Metrike:** top-1 in top-k natančnost, stopnja pravilnega povezovanja, delež unikatnih pri k točkah.

### 6.2 Napad na članstvo / MIA (Carlini 2022)
- **Cilj:** ali je bila konkretna pot v učni množici generatorja.
- **Predznanje:** referenčna pot; dostop do modela ali njegovih izhodov (senčni modeli).
- **Obseg:** `synthetic`.
- **Pristop:** LiRA – nauči N senčnih generatorjev z/brez tarče, oceni likelihood-ratio.
- **Metrike:** **TPR pri nizkem FPR** (npr. FPR = 0.001, 0.01), AUC, FPR pri FNR = 0.1. (TPR@nizek FPR je pravilnejši od AUC – tako priporoča Carlini.)

### 6.3 Rekonstrukcija / inverzija (Buchholz 2022)
- **Cilj:** oceniti dejanske lokacije iz zašumljenih poti.
- **Predznanje:** poznan mehanizem in parametri, delna porazdelitev vhoda.
- **Obseg:** `protected` (perturbacijske metode).
- **Pristop:** Bayesovska/MAP inverzija znanega mehanizma šuma; za omrežne poti dekodiranje po grafu.
- **Metrike:** Hausdorffova razdalja, DTW, povprečna prostorska napaka (m), ujemanje segmentov (edge recall/precision).

### 6.4 Sklepanje o lastnostih / POI (Primault 2019)
- **Cilj:** iz zaščitenih/sintetičnih poti sklepati o občutljivih lastnostih (dom, delo, rutina, POI).
- **Predznanje:** zunanji POI sloj, statistični vzorci gibanja, klasifikator atributov.
- **Obseg:** `protected`, `synthetic`.
- **Pristop:** detekcija home/work prek stay-point clustering; klasifikator atributov na značilkah gibanja.
- **Metrike:** balanced accuracy, F1, precision, recall; napaka pri oceni pogostih lokacij (razdalja do resničnega doma/dela).

**Uporabnostne metrike (za trade-off):** Jensen-Shannon nad porazdelitvijo obiskov celic, napaka OD-matrik, ohranjenost porazdelitve dolžin/trajanja/hitrosti, query error nad range-count poizvedbami.

---

## 7. Anonimizacijski / zaščitni pristopi

Vsak je izvedba `PrivacyMechanism`. V MVP-ju implementiraš `NoProtection` + eno perturbacijo; ostali so razširitev.

| Mehanizem | Garancija | Ključni parametri | Deluje na pogledu | Referenca/opomba |
| --- | --- | --- | --- | --- |
| `NoProtection` | none | – | katerikoli | baseline (zgornja meja tveganja) |
| `SpatialRounding` / grid | none | velikost celice | GPS/celice | generalizacija |
| `TemporalDownsampling` | none | interval / delež | GPS | redčenje |
| `GaussianNoise` / `LaplaceNoise` | ~ | σ / b | GPS | naiven prostorski šum |
| `GeoIndistinguishability` | geo-ind (ε) | ε (planar Laplace) | GPS | Andrés 2013 |
| `PointLDP` | LDP (ε) | ε, grid | celice | randomized response nad celicami |
| `SquareWave` | LDP (ε) | ε | numerične vrednosti | Li 2020 (za porazdelitve) |
| `SegmentPerturbation` | ~ | verjetnost zamenjave | segmenti | omrežno-zavedno |
| `KAnonymityTraj` | k-anon | k | poti/skupine | dummy/microaggregation |
| `DPTGenerator`* | central-DP | ε, višina hierarhije | celice | He 2015 (baseline sinteza) |
| `AdaTrace`* | central-DP | ε | celice/OD | Gursoy 2018 |
| `DiffRNTraj`* / `ControlTraj`* | – | model params | segmenti | diffusion, omrežno-zavedno |
| `RNLDPSynth` | LDP (ε) | ε, omrežni parametri | segmenti | **tvoj mehanizem** (hook) |
| kombinirani | mešano | – | – | npr. downsampling + LDP + map-matching |

*označeni so hkrati generatorji (`SyntheticGenerator`), ne le perturbacije – v modelu se pojavijo v Synthetic Layer.

RN-LDP-Synth vključiš kot navadno izvedbo vmesnika, ko bo pripravljen; benchmark ga bo primerjal z zgornjimi baseline-i pod enakimi pogoji (ravno to je namen okolja).

---

## 8. Primer konfiguracijske datoteke

`config/exp_geolife_geoind_reid.yaml`:

```yaml
experiment:
  id: geolife_geoind_reid_v1
  seed: 42
  output_dir: results/geolife_geoind_reid_v1

map:
  source: osm
  region: beijing            # SKLADNO z Geolife
  bbox: [116.20, 39.75, 116.55, 40.05]
  crs: EPSG:32650

dataset:
  id: geolife
  path: data/raw/geolife
  native_region: beijing     # orkestrator preveri map.region == native_region

cleaning:
  max_speed_kmh: 200
  min_points: 20
  min_length_m: 500
  resample_s: 5
  bbox_filter: from_map

map_matching:
  matcher: fmm
  k_candidates: 8
  radius_m: 50
  gps_error_m: 20
  min_match_score: 0.6

split:
  scheme: by_user
  fractions: {train: 0.5, test: 0.2, shadow: 0.2, attack: 0.1}

privacy_mechanisms:
  - id: none
  - id: geo_indistinguishability
    params: {epsilon: [0.1, 1.0, 10.0]}   # grid parametrov

synthetic_generators: []      # ni sinteze v tem eksperimentu

attacks:
  - type: reidentification
    attacker:
      known_points: [3, 5, 10]            # koliko točk tarče pozna napadalec
      distance: dtw
    target_scope: [raw, protected]

metrics:
  privacy: [top1_acc, topk_acc, linkage_rate]
  utility: [cell_js_divergence, length_dist_error]
  bootstrap: {n: 1000, ci: 0.95}

reporting:
  export: [csv, parquet]
  plots: [tradeoff, risk_matrix]
```

Orkestrator razreši mrežo parametrov (`epsilon × known_points`) v posamezne run-e, vsak s svojim verzijskim ključem.

---

## 9. Predlagana struktura repozitorija

```
trajguard/
├── config/                  # YAML/JSON eksperimenti + privzete sheme
│   ├── experiments/
│   └── defaults/
├── data/
│   ├── raw/                 # nedotaknjene izvorne zbirke (Geolife, T-Drive, Porto)
│   ├── interim/             # očiščene poti (CleanTrajectory)
│   ├── processed/           # map-matchane poti (MatchedTrajectory)
│   ├── protected/           # zaščitene verzije
│   └── synthetic/           # sintetične poti
├── maps/                    # zgrajeni cestni grafi (Beijing, Ljubljana, Porto)
├── src/trajguard/
│   ├── maps/                # MapSource + OSM izvedba
│   ├── datasets/            # DatasetLoader + Geolife/T-Drive/Porto
│   ├── matching/            # MapMatcher + fmm/leuven
│   ├── representation/      # TrajectoryView (adapterji)
│   ├── privacy/             # PrivacyMechanism + mehanizmi
│   ├── synthesis/           # SyntheticGenerator + generatorji
│   ├── attacks/             # Attack + 4 družine napadov
│   ├── evaluation/          # Metric + Evaluation Engine
│   ├── experiments/         # Orchestrator, registry, seeding, versioning
│   ├── reporting/           # izvoz, grafi, tabele
│   └── datamodel/           # dataclass/pydantic sheme entitet
├── notebooks/               # raziskovalne analize, sanity-check vizualizacije
├── results/                 # izhodi eksperimentov (CSV/Parquet/grafi)
├── reports/                 # generirana poročila (Markdown/LaTeX)
├── tests/                   # unit + integracijski testi (majhen fixture dataset)
├── pyproject.toml
└── README.md
```

Namen map: `raw` je nespremenljiv (nikoli ne pišeš vanj); `interim`/`processed`/`protected`/`synthetic` so cache-i, brisljivi in ponovno generljivi iz konfiguracij; `maps` loči drage OSM gradnje od podatkov; `src/.../<modul>` zrcali sloje iz §2; `tests` uporablja miniaturno zbirko (npr. 20 poti), da CI teče v sekundah.

---

## 10. MVP verzija

Cilj: **prvi rezultati za IZV do konca S2–S3**, brez gradnje celotnega ogrodja.

**Obseg MVP:**
- **1 mapa:** OSM Beijing (skladna z Geolife). *(OSM Ljubljana pripraviš vzporedno za kasnejše sintetične poti, a ni na kritični poti napadov.)*
- **1 zbirka:** Geolife (vzorec, npr. 30–50 uporabnikov).
- **Čiščenje:** hitrostni prag + min. dolžina + resampling.
- **Map matching:** `fmm` z default parametri, filter po match score.
- **Baseline brez zaščite:** `NoProtection`.
- **1 perturbacija:** `GeoIndistinguishability` (planar Laplace), ε ∈ {0.1, 1, 10}.
- **1 preprost generator:** Markov/n-gram nad sekvencami segmentov (da ima MIA tarčo brez težkega diffusion modela).
- **3 napadi:** reidentifikacija (na raw + protected), MIA (na synthetic), rekonstrukcija (na protected).
- **Osnovne metrike:** top-k natančnost, TPR@FPR (AUC), povprečna prostorska napaka + Hausdorff.
- **Poročilo:** en Markdown izpis z matriko tveganj in eno tradeoff krivuljo.

**Kaj v MVP-ju NAMERNO izpustiš:** federativne pristope, k-anonimnost, ControlTraj/Diff-RNTraj, attribute inference, več map hkrati, PostGIS. Vse to je horizont B.

**Definicija dokončanosti MVP:** en `yaml` požene celoten cevovod od surovega Geolife do matrike tveganj z bootstrap CI, ponovljivo prek seeda.

---

## 11. Razširitveni načrt po sprintih

Poravnano s tvojima načrtoma dela (IZV mejniki S0–S6). NPZ (pregled literature) teče vzporedno in **napaja izbor baseline mehanizmov** za to okolje.

| Sprint | Okolje (IZV) | Povezava z NPZ |
| --- | --- | --- |
| **S0** | Model groženj, tipologija napadalcev; skeleti vmesnikov + registry; datamodel | kategorizacija prvih 20 člankov |
| **S1** | Map Manager (OSM Beijing + Ljubljana), Dataset Manager (Geolife), čiščenje, map-matching | anonimizacijski pristopi → seznam baseline-ov |
| **S2** | Reidentifikacija na nezaščitenih; prvi rezultati; Evaluation Engine (osnovne metrike + CI) | centralna/lokalna DP → kandidati za Privacy Layer |
| **S3** | GeoInd + rekonstrukcija; MIA + preprost generator; napadi na zaščitenih | generativni/federativni pristopi → generator hooki |
| **S4** | Orkestrator z mrežami parametrov; sistematične simulacije; več mehanizmov | primerjalna matrika (model zaupanja, omrežje, izhod) |
| **S5** | Statistična analiza, tradeoff/Pareto, vizualizacije, poročilo o tveganjih (~20 str.) | opisni pregled + priporočila |
| **S6** | Zaključno poročilo; motivacijski del za uvod članka RN-LDP-Synth | Related work sekcija |
| **2. letnik** | Horizont B: RN-LDP-Synth kot mehanizem, diffusion generatorji, T-Drive/Porto, PostGIS, polni benchmark | – |

---

## 12. Tveganja in mitigacije

Poleg tveganj iz tvojih načrtov dela (izbran napad se izkaže za nesmiselnega; računsko predrago; nerealistično predznanje) dodajam **tehnična tveganja okolja**:

**T1 – Neskladje mape in zbirke (visoka verjetnost, visok vpliv).** Map-matching Geolife na Ljubljano bi tiho proizvedel smeti. *Mitigacija:* orkestrator zavrne konfiguracijo, kjer `map.region != dataset.native_region`; OSM Ljubljana rezerviran za sintetične poti/RN-LDP-Synth.

**T2 – Slaba kakovost map-matchinga na redkih GPS (Geolife ima nizko frekvenco za nekatere uporabnike).** *Mitigacija:* filter po `match_score`, poročaj delež zavrženih poti; parametre matcherja (radij, GPS error) nastavi eksperimentalno na majhnem vzorcu.

**T3 – Nepošten MIA zaradi puščanja train/test.** *Mitigacija:* delitev enkrat na CleanTrajectory ravni, propagacija split oznake skozi vse artefakte; senčni modeli se učijo strogo na svojih delih.

**T4 – Neponovljivost (seedi, verzije OSM, verzije knjižnic).** *Mitigacija:* fiksni seedi v konfiguraciji, verzijski ključi po hash-u, zapis OSM timestamp in `git_commit`, zaklenjen `pyproject.toml`.

**T5 – Računska cena LiRA (N senčnih generatorjev × ε mreža).** *Mitigacija:* najprej pilotni run z majhnim N; velikost zbirke in N prilagodi, odločitve zabeleži (kot v tvojem načrtu, Tveganje 2).

**T6 – Nejasne/nekonsistentne definicije v literaturi (iz NPZ).** *Mitigacija:* vsak mehanizem v kodi nosi eksplicitno `guarantee` oznako in dokumentiran privzetek predpostavke; primerjaš le mehanizme z združljivim modelom zaupanja.

**T7 – Prehitro posploševanje "anonimizacija deluje".** *Mitigacija:* rezultate vedno poročaj z bootstrap CI in vezano na konkreten napad + ε; matrika tveganj namesto enotne trditve.

---

## 13. Priporočila za prvo implementacijo

1. **Začni z vmesniki in datamodelom (S0), ne z napadi.** Petih abstraktnih razredov iz §2.3 + `registry` je ~1 dan dela in določi vse kasnejše dodajanje. To ti prihrani prepisovanje v 2. letniku.
2. **Ena navpična rezina najprej.** Geolife → OSM Beijing → čiščenje → matching → `NoProtection` → reidentifikacija → top-k. Šele ko ta cevovod teče od `yaml`-a do rezultata, dodajaj širino. To je edini pravi test arhitekture.
3. **Map-matching preveri vizualno na 5–10 poteh v notebooku, preden ga poženeš na vsem.** Newson & Krumm HMM je občutljiv na parametre; `fmm` je hiter, a `leuvenmapmatching` je lažje debugirati – za prvo kalibracijo priporočam slednjega, za produkcijske run-e `fmm`.
4. **Shrani vse kot Parquet + DuckDB od začetka.** Ne uvajaj PostGIS v MVP-ju; DuckDB nad Parquet ti da SQL nad prostorskimi tabelami brez strežnika.
5. **MLflow priključi takoj (S0/S1).** Vsak run naj beleži config hash, seed, metrike – ceneje je od začetka kot naknadno.
6. **Testni fixture (20 poti) v `tests/`** za integracijski test celotnega cevovoda; CI mora teči v sekundah, sicer ga nehaš poganjati.
7. **RN-LDP-Synth pusti kot prazen hook** (`class RNLDPSynth(PrivacyMechanism): raise NotImplementedError`) – okolje mora biti sposobno primerjati baseline-e brez njega; tvoj mehanizem se priključi, ko bo pripravljen, brez sprememb jedra.

---

### Priloga: preslikava na tvoje reference

Napadi in mehanizmi v tej zasnovi so vezani na že potrjene vire iz načrtov dela: reidentifikacija → de Montjoye 2013; MIA → Carlini 2022; rekonstrukcija → Buchholz 2022; pregled/atributi → Primault 2019; baseline sinteza → He 2015 (DPT), Gursoy 2018 (AdaTrace); omrežno-zavedna sinteza → Wei 2024 (Diff-RNTraj), Zhu 2024 (ControlTraj); LDP baseline → Ioannou 2024, Qian 2025, Zhang 2024. Map-matching → Newson & Krumm 2009.

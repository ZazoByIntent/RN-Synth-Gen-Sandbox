"""Frozen dataclass schemas for the trajguard data model (design doc §4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import geopandas as gpd
    import networkx as nx

Bbox = tuple[float, float, float, float]
"""Bounding box as (min_lon, min_lat, max_lon, max_lat)."""


@dataclass(frozen=True, slots=True)
class Point:
    """One GPS sample of a trajectory."""

    lat: float
    lon: float
    t: datetime
    alt: float | None = None


@dataclass(frozen=True, slots=True)
class MatchedPoint:
    """A GPS sample projected onto a road edge, in the map's projected CRS."""

    x: float
    y: float
    t: datetime
    offset_m: float


@dataclass(frozen=True, slots=True)
class Map:
    """A prepared road-network map artefact and where it is stored."""

    map_id: str
    source: str  # "osm" | "synthetic"
    region: str
    bbox: Bbox
    crs: str
    osm_timestamp: datetime | None
    path_graph: str
    path_edges: str
    path_nodes: str


@dataclass(frozen=True, slots=True)
class RawTrajectory:
    """A trajectory as imported from the source files, before cleaning."""

    traj_id: str
    user_id: str
    dataset_id: str
    points: tuple[Point, ...]
    start_t: datetime
    end_t: datetime
    n_points: int
    source_file: str


@dataclass(frozen=True, slots=True)
class CleanTrajectory:
    """A cleaned trajectory with derived statistics and its split assignment."""

    traj_id: str
    user_id: str
    points: tuple[Point, ...]
    bbox: Bbox
    duration_s: float
    length_m: float
    mean_speed: float
    cleaning_flags: tuple[str, ...]
    split: str  # "train" | "test" | "shadow" | "attack"


@dataclass(frozen=True, slots=True)
class MatchedTrajectory:
    """A trajectory map-matched onto road edges of a specific map."""

    traj_id: str
    user_id: str
    map_id: str
    edge_seq: tuple[int, ...]
    matched_points: tuple[MatchedPoint, ...]
    match_score: float
    frac_matched: float


@dataclass(frozen=True, slots=True)
class ProtectedTrajectory:
    """The output of a privacy mechanism applied to a source trajectory."""

    traj_id: str
    source_traj_id: str
    mechanism_id: str
    params_hash: str
    guarantee: str  # "none" | "geo-ind" | "ldp" | "central-dp" | "k-anon"
    epsilon: float | None
    payload: object  # representation depends on the view the mechanism works on
    map_id: str


@dataclass(frozen=True, slots=True)
class SyntheticTrajectory:
    """A trajectory produced by a generative model."""

    syn_id: str
    generator_id: str
    params_hash: str
    payload: object  # representation depends on the generator's view
    trained_on_split: str  # reference to the training split (for fair MIA)
    map_id: str


@dataclass(frozen=True, slots=True)
class AttackResult:
    """Raw output of one attack run, before metric computation."""

    result_id: str
    attack_id: str
    exp_id: str
    target_data_ref: str
    predictions: object  # attack-specific prediction structure
    scores: object  # attack-specific confidence scores
    ground_truth_ref: str
    runtime_s: float


@dataclass(frozen=True, slots=True)
class MetricValue:
    """A single metric value with an optional bootstrap confidence interval."""

    metric_id: str
    result_id: str
    name: str
    value: float
    ci_low: float | None
    ci_high: float | None
    n_bootstrap: int | None


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    """Identifying metadata of one experiment run (design doc §4, Experiment)."""

    exp_id: str
    config_hash: str
    map_id: str
    dataset_id: str
    seed: int
    git_commit: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RoadNetwork:
    """Road graph plus node/edge tables, in the map's projected CRS."""

    graph: nx.MultiDiGraph[int]  # nodes keyed by OSM node id
    nodes: gpd.GeoDataFrame
    edges: gpd.GeoDataFrame
    crs: str
    region: str


class TrajectoryView:
    """Adapter over a trajectory's representations; skeletal until P3."""


class BackgroundKnowledge:
    """Attacker's auxiliary knowledge for an attack; skeletal until P4."""

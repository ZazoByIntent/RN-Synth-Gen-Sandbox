"""Tests for LeuvenMapMatcher on the fixture network."""

import json
from datetime import datetime, timedelta
from itertools import pairwise
from pathlib import Path

import pytest

from trajguard.datamodel import CleanTrajectory, MatchedTrajectory, Point, RoadNetwork
from trajguard.datasets import CleaningConfig, GeolifeLoader, clean
from trajguard.experiments import registry
from trajguard.maps import OSMMapSource
from trajguard.matching import LeuvenMapMatcher, mean_offset_m, passes_quality

FIXTURES = Path(__file__).parent / "fixtures"
MANIFEST = json.loads((FIXTURES / "geolife" / "MANIFEST.json").read_text(encoding="utf-8"))
AREA = tuple(MANIFEST["area_west_south_east_north"])
GOLDEN_ID = "000_20090516091038"
# Pinned on the committed fixture network with default matcher parameters
# (regenerate by matching the golden track and printing .edge_seq).
GOLDEN_EDGE_SEQ = (
    7120, 1670, 1639, 1632, 1635, 4550, 4554, 7601,
    1628, 1623, 91, 2316, 4491, 4496, 8938, 4496,
)


@pytest.fixture(scope="module")
def net() -> RoadNetwork:
    return OSMMapSource(
        region="beijing", bbox=AREA, crs="EPSG:32650", maps_dir=FIXTURES / "maps"
    ).load()


@pytest.fixture(scope="module")
def golden_clean() -> CleanTrajectory:
    for raw in GeolifeLoader(FIXTURES / "geolife").iter_trajectories():
        if raw.traj_id == GOLDEN_ID:
            cleaned = clean(raw, CleaningConfig())
            assert cleaned is not None
            return cleaned
    pytest.fail(f"golden trajectory {GOLDEN_ID} missing from fixture")


@pytest.fixture(scope="module")
def golden_match(net: RoadNetwork, golden_clean: CleanTrajectory) -> MatchedTrajectory:
    return LeuvenMapMatcher().match(golden_clean, net)


def test_registered_in_registry() -> None:
    assert registry.get("matcher", "leuven") is LeuvenMapMatcher


def test_golden_trajectory_produces_expected_edge_sequence(
    golden_match: MatchedTrajectory, golden_clean: CleanTrajectory
) -> None:
    assert golden_match.edge_seq == GOLDEN_EDGE_SEQ
    assert golden_match.frac_matched == 1.0
    assert golden_match.match_score > 0.9
    assert len(golden_match.matched_points) == len(golden_clean.points)
    assert passes_quality(golden_match)


def test_golden_match_quality(golden_match: MatchedTrajectory) -> None:
    assert mean_offset_m(golden_match) < 20  # metres; GPS-to-road distance
    assert all(p.offset_m <= 150 for p in golden_match.matched_points)
    timestamps = [p.t for p in golden_match.matched_points]
    assert timestamps == sorted(timestamps)


def test_golden_edge_sequence_is_a_connected_path(
    golden_match: MatchedTrajectory, net: RoadNetwork
) -> None:
    index = list(net.edges.index)
    node_pairs = [(index[e][0], index[e][1]) for e in golden_match.edge_seq]
    for (_, prev_v), (next_u, _) in pairwise(node_pairs):
        assert prev_v == next_u


def test_match_is_deterministic(net: RoadNetwork, golden_clean: CleanTrajectory) -> None:
    a = LeuvenMapMatcher().match(golden_clean, net)
    b = LeuvenMapMatcher().match(golden_clean, net)
    assert a.edge_seq == b.edge_seq
    assert a.match_score == b.match_score


def test_offroad_trajectory_fails_quality(net: RoadNetwork) -> None:
    t0 = datetime(2009, 1, 1, 12, 0, 0)
    points = tuple(
        Point(lat=39.985, lon=116.25 + i * 0.0002, t=t0 + timedelta(seconds=10 * i))
        for i in range(25)
    )  # west of the fixture area: no edges anywhere near
    fake = CleanTrajectory(
        traj_id="offroad", user_id="x", points=points, bbox=(116.25, 39.98, 116.26, 39.99),
        duration_s=240.0, length_m=600.0, mean_speed=2.5, cleaning_flags=(),
        split="unassigned",
    )
    matched = LeuvenMapMatcher().match(fake, net)
    assert matched.match_score == 0.0
    assert matched.edge_seq == ()
    assert not passes_quality(matched)


def test_passes_quality_threshold_boundary(golden_match: MatchedTrajectory) -> None:
    assert passes_quality(golden_match, min_match_score=0.9)
    assert not passes_quality(golden_match, min_match_score=0.99)

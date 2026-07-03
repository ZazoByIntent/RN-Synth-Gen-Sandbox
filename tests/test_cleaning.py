"""Tests for trajectory cleaning against the manifest's expected outcomes."""

import json
from itertools import pairwise
from pathlib import Path

import pytest

from trajguard.datamodel import RawTrajectory
from trajguard.datasets import CleaningConfig, GeolifeLoader, clean
from trajguard.datasets.cleaning import SPEED_FILTERED, haversine_m

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "geolife"
MANIFEST = json.loads((FIXTURE_ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
CFG = CleaningConfig()  # defaults must match MANIFEST["cleaning_defaults"]


@pytest.fixture(scope="module")
def trajectories() -> dict[str, RawTrajectory]:
    return {t.traj_id: t for t in GeolifeLoader(FIXTURE_ROOT).iter_trajectories()}


def test_defaults_match_manifest() -> None:
    recorded = MANIFEST["cleaning_defaults"]
    assert recorded == {
        "max_speed_kmh": CFG.max_speed_kmh,
        "min_points": CFG.min_points,
        "min_length_m": CFG.min_length_m,
        "resample_s": CFG.resample_s,
    }


@pytest.mark.parametrize("entry", MANIFEST["files"], ids=lambda e: e["traj_id"])
def test_expected_outcome(entry: dict, trajectories: dict[str, RawTrajectory]) -> None:
    result = clean(trajectories[entry["traj_id"]], CFG)
    if entry["expected"] == "kept":
        assert result is not None
        assert list(result.cleaning_flags) == entry["expected_flags"]
    else:
        assert result is None  # known outliers are removed


def test_speed_spikes_are_filtered_out(trajectories: dict[str, RawTrajectory]) -> None:
    spikes = [f for f in MANIFEST["files"] if f["category"] == "spike"]
    assert spikes, "fixture must contain speed-spike trajectories"
    for entry in spikes:
        raw = trajectories[entry["traj_id"]]
        assert entry["max_raw_segment_speed_kmh"] > CFG.max_speed_kmh
        result = clean(raw, CFG)
        assert result is not None
        assert SPEED_FILTERED in result.cleaning_flags
        assert len(result.points) < raw.n_points
        for a, b in pairwise(result.points):
            dt = (b.t - a.t).total_seconds()
            assert haversine_m(a, b) / dt * 3.6 <= CFG.max_speed_kmh


def test_kept_tracks_are_resampled_and_long_enough(
    trajectories: dict[str, RawTrajectory],
) -> None:
    for entry in (f for f in MANIFEST["files"] if f["expected"] == "kept"):
        result = clean(trajectories[entry["traj_id"]], CFG)
        assert result is not None
        assert len(result.points) >= CFG.min_points
        assert result.length_m >= CFG.min_length_m
        assert result.duration_s > 0 and result.mean_speed > 0
        west, south, east, north = result.bbox
        assert west <= east and south <= north
        for a, b in pairwise(result.points):
            assert (b.t - a.t).total_seconds() >= CFG.resample_s


def test_clean_is_deterministic(trajectories: dict[str, RawTrajectory]) -> None:
    traj_id = next(f["traj_id"] for f in MANIFEST["files"] if f["expected"] == "kept")
    assert clean(trajectories[traj_id], CFG) == clean(trajectories[traj_id], CFG)

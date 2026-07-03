"""Tests for GeolifeLoader against the committed real-data fixture."""

import json
from datetime import datetime
from pathlib import Path

from trajguard.datasets import GeolifeLoader
from trajguard.experiments import registry

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "geolife"
MANIFEST = json.loads((FIXTURE_ROOT / "MANIFEST.json").read_text(encoding="utf-8"))


def _load_all() -> dict[str, object]:
    return {t.traj_id: t for t in GeolifeLoader(FIXTURE_ROOT).iter_trajectories()}


def test_registered_in_registry() -> None:
    assert registry.get("dataset", "geolife") is GeolifeLoader


def test_native_region_is_beijing() -> None:
    assert GeolifeLoader(FIXTURE_ROOT).native_region == "beijing"


def test_trajectory_count_and_ids_match_manifest() -> None:
    trajs = _load_all()
    assert len(trajs) == len(MANIFEST["files"])
    assert set(trajs) == {f["traj_id"] for f in MANIFEST["files"]}


def test_point_counts_and_first_points_match_manifest() -> None:
    trajs = _load_all()
    for entry in MANIFEST["files"]:
        traj = trajs[entry["traj_id"]]
        assert traj.n_points == entry["n_data_lines"]
        first = traj.points[0]
        assert first.lat == entry["first_point"]["lat"]
        assert first.lon == entry["first_point"]["lon"]
        assert first.t == datetime.fromisoformat(entry["first_point"]["time"])
        assert traj.start_t == first.t
        assert traj.end_t == traj.points[-1].t


def test_iteration_is_deterministic() -> None:
    loader = GeolifeLoader(FIXTURE_ROOT)
    first = [t.traj_id for t in loader.iter_trajectories()]
    second = [t.traj_id for t in loader.iter_trajectories()]
    assert first == second
    assert sorted(first) == first  # sorted (user, file) order


def test_invalid_altitude_sentinel_and_feet_conversion(tmp_path: Path) -> None:
    plt = tmp_path / "Data" / "042" / "Trajectory" / "20080101000000.plt"
    plt.parent.mkdir(parents=True)
    header = "\n".join(["Geolife trajectory", "WGS 84", "Altitude is in Feet", "", "0,2,255", ""])
    plt.write_text(
        header + "\n39.9,116.3,0,-777,39448.0,2008-01-01,00:00:00\n"
        "39.9,116.3,0,100,39448.00002,2008-01-01,00:00:02\n",
        encoding="utf-8",
    )
    (traj,) = GeolifeLoader(tmp_path).iter_trajectories()
    assert traj.points[0].alt is None  # -777 sentinel
    assert traj.points[1].alt == 100 * 0.3048  # feet -> metres
    assert traj.user_id == "042"

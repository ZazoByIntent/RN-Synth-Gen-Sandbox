"""One-off builder for the committed P1 test fixtures. CI never runs this.

Provenance script: downloads Geolife Trajectories 1.3 (Microsoft Research,
MSR-LA research-use license) and a small OSM slice of Haidian, Beijing via
Overpass, then writes the committed fixtures:

- ``geolife/Data/<uid>/Trajectory/*.plt`` — ~20 truncated *real* trajectories:
  dense kept tracks, too-short tracks, a stay-point track that keeps enough
  points but covers too little distance (min_length_m rejection), and tracks
  with a natural GPS speed spike.
- ``geolife/MANIFEST.json`` — per-file provenance and the expected ``clean()``
  outcome the tests assert against.
- ``maps/beijing/graph.graphml`` (+ Parquet sidecars) — drive network for the
  fixture area, projected to EPSG:32650, produced via ``OSMMapSource.load()``.

Usage: ``uv run python tests/fixtures/build_fixtures.py <path-to-geolife.zip>``
Selection is fully deterministic: sorted scan order, first-match quotas.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

from trajguard.datamodel import Point, RawTrajectory
from trajguard.datasets.cleaning import (
    RESAMPLED,
    SPEED_FILTERED,
    CleaningConfig,
    _filter_speed,
    _resample,
    clean,
    haversine_m,
)
from trajguard.maps.osm import OSMMapSource

GEOLIFE_URL = (
    "https://download.microsoft.com/download/F/4/8/"
    "F4894AA5-FDBC-481E-9285-D5F8C4C4F039/Geolife%20Trajectories%201.3.zip"
)
LICENSE_NOTE = "Geolife Trajectories 1.3, Microsoft Research; MSR-LA, research use only."

# Fixture area: Haidian around Tsinghua/Wudaokou — (west, south, east, north).
AREA = (116.30, 39.97, 116.34, 40.00)
HEADER_LINES = 6
TRUNC_LINES = 150  # kept/spike fixtures: first N data lines
SHORT_LINES = 10  # below min_points=20 even before thinning
SLOW_WINDOWS = (60, 80, 100)  # candidate prefixes for a stay-point/min_length reject
QUOTAS = {"kept": 14, "spike": 2, "short": 3, "slow": 1}
MAX_SCAN_USERS = 60

FIXTURE_ROOT = Path(__file__).parent
CFG = CleaningConfig()


@dataclass
class Candidate:
    """One source .plt considered for the fixture set."""

    member: str
    user_id: str
    header: list[str]
    data_lines: list[str]


def _parse_lines(lines: list[str]) -> list[Point]:
    points = []
    for line in lines:
        lat, lon, _, _alt, _, date, time = line.split(",")
        points.append(Point(float(lat), float(lon), datetime.fromisoformat(f"{date}T{time}")))
    return points


def _in_area(points: list[Point]) -> bool:
    west, south, east, north = AREA
    return all(west <= p.lon <= east and south <= p.lat <= north for p in points)


def _max_segment_speed_kmh(points: list[Point]) -> float:
    best = 0.0
    for a, b in pairwise(points):
        dt = (b.t - a.t).total_seconds()
        if dt > 0:
            best = max(best, haversine_m(a, b) / dt * 3.6)
    return best


def _raw(points: list[Point], traj_id: str) -> RawTrajectory:
    return RawTrajectory(
        traj_id=traj_id,
        user_id="fixture",
        dataset_id="geolife",
        points=tuple(points),
        start_t=points[0].t,
        end_t=points[-1].t,
        n_points=len(points),
        source_file=traj_id,
    )


def _classify(cand: Candidate, quotas: dict[str, int]) -> tuple[str, int] | None:
    """Return (category, n_lines_to_keep) if this candidate fills an open quota."""
    if len(cand.data_lines) < TRUNC_LINES:
        return None
    trunc = _parse_lines(cand.data_lines[:TRUNC_LINES])
    speed = _max_segment_speed_kmh(trunc)
    result = clean(_raw(trunc, cand.member), CFG)

    if (
        quotas["spike"]
        and speed > 250
        and result is not None
        and SPEED_FILTERED in result.cleaning_flags
    ):
        return ("spike", TRUNC_LINES)
    if not _in_area(trunc):
        return None
    if quotas["slow"]:
        # Before the kept-quality gate: a stay-point track fails clean() on its
        # full prefix, yet a window of it is exactly the min_length_m reject case.
        n_lines = _slow_window(cand)
        if n_lines is not None:
            return ("slow", n_lines)
    if result is None or SPEED_FILTERED in result.cleaning_flags:
        return None
    if quotas["kept"]:
        return ("kept", TRUNC_LINES)
    if quotas["short"]:
        return ("short", SHORT_LINES)
    return None


def _pipeline(points: list[Point]) -> tuple[Point, ...]:
    return _resample(_filter_speed(tuple(points), CFG.max_speed_kmh, []), CFG.resample_s, [])


def _slow_window(cand: Candidate) -> int | None:
    """Smallest prefix that keeps >= min_points after cleaning yet fails min_length."""
    for n_lines in SLOW_WINDOWS:
        if n_lines > len(cand.data_lines):
            return None
        prefix = _parse_lines(cand.data_lines[:n_lines])
        after = _pipeline(prefix)
        if len(after) >= CFG.min_points and clean(_raw(prefix, cand.member), CFG) is None:
            return n_lines
    return None


def _expected_outcome(points: list[Point], traj_id: str) -> tuple[str, list[str]]:
    result = clean(_raw(points, traj_id), CFG)
    if result is not None:
        return ("kept", list(result.cleaning_flags))
    # The drop reason depends on the point count *after* filtering/thinning.
    if len(_pipeline(points)) < CFG.min_points:
        return ("dropped_min_points", [])
    return ("dropped_min_length", [])


def _iter_candidates(zf: zipfile.ZipFile) -> list[Candidate]:
    users = sorted(
        {n.split("/")[2] for n in zf.namelist() if n.count("/") >= 3 and n.endswith(".plt")}
    )[:MAX_SCAN_USERS]
    out = []
    for name in sorted(zf.namelist()):
        parts = name.split("/")
        if not name.endswith(".plt") or len(parts) < 5 or parts[2] not in users:
            continue
        with zf.open(name) as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace")
            lines = []
            for i, line in enumerate(text):
                if i >= HEADER_LINES + TRUNC_LINES:
                    break
                lines.append(line.rstrip("\r\n"))
        if len(lines) <= HEADER_LINES:
            continue
        out.append(Candidate(name, parts[2], lines[:HEADER_LINES], lines[HEADER_LINES:]))
    return out


def build_geolife(zip_path: Path) -> None:
    """Select fixtures from the Geolife zip and write .plt files + manifest."""
    quotas = dict(QUOTAS)
    manifest_files = []
    shutil.rmtree(FIXTURE_ROOT / "geolife" / "Data", ignore_errors=True)
    with zipfile.ZipFile(zip_path) as zf:
        for cand in _iter_candidates(zf):
            if not any(quotas.values()):
                break
            picked = _classify(cand, quotas)
            if picked is None:
                continue
            category, n_lines = picked
            quotas[category] -= 1

            data = cand.data_lines[:n_lines]
            points = _parse_lines(data)
            stem = Path(cand.member).stem
            rel = Path("Data") / cand.user_id / "Trajectory" / f"{stem}.plt"
            dest = FIXTURE_ROOT / "geolife" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("\n".join(cand.header + data) + "\n", encoding="utf-8")

            expected, flags = _expected_outcome(points, str(rel))
            manifest_files.append(
                {
                    "file": str(rel),
                    "traj_id": f"{cand.user_id}_{stem}",
                    "user_id": cand.user_id,
                    "source_member": cand.member,
                    "category": category,
                    "n_data_lines": len(data),
                    "first_point": {
                        "lat": points[0].lat,
                        "lon": points[0].lon,
                        "time": points[0].t.isoformat(),
                    },
                    "max_raw_segment_speed_kmh": round(_max_segment_speed_kmh(points), 1),
                    "expected": expected,
                    "expected_flags": flags,
                }
            )

    if any(quotas.values()):
        sys.exit(f"quotas not filled: {quotas} — widen AREA or MAX_SCAN_USERS")

    manifest = {
        "source_url": GEOLIFE_URL,
        "license": LICENSE_NOTE,
        "area_west_south_east_north": AREA,
        "created": datetime.now(tz=UTC).date().isoformat(),
        "cleaning_defaults": {
            "max_speed_kmh": CFG.max_speed_kmh,
            "min_points": CFG.min_points,
            "min_length_m": CFG.min_length_m,
            "resample_s": CFG.resample_s,
        },
        "resampled_flag": RESAMPLED,
        "speed_filtered_flag": SPEED_FILTERED,
        "files": manifest_files,
    }
    path = FIXTURE_ROOT / "geolife" / "MANIFEST.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(manifest_files)} fixtures + {path}")


def build_map_slice() -> None:
    """Download the fixture-area network via OSMMapSource (real code path).

    network_type="all": Geolife is mixed-mode (walk/bike/bus/car) — matching
    against a drive-only graph leaves pedestrian tracks 30-80 m off-road (P2
    calibration finding), so footpaths must be part of the network.
    """
    source = OSMMapSource(
        region="beijing",
        bbox=AREA,
        crs="EPSG:32650",
        network_type="all",
        maps_dir=FIXTURE_ROOT / "maps",
    )
    net = source.load()
    print(f"map slice: {len(net.nodes)} nodes, {len(net.edges)} edges -> {source.graphml_path}")


if __name__ == "__main__":
    build_geolife(Path(sys.argv[1]))
    build_map_slice()

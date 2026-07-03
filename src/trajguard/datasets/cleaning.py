"""Cleaning of raw trajectories: speed filter, resampling, minimum-size checks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise

from trajguard.datamodel import Bbox, CleanTrajectory, Point, RawTrajectory

_EARTH_RADIUS_M = 6_371_000.0
SPEED_FILTERED = "speed_filtered"
RESAMPLED = "resampled"


@dataclass(frozen=True, slots=True)
class CleaningConfig:
    """Thresholds for trajectory cleaning (defaults from design doc §8)."""

    max_speed_kmh: float = 200.0
    min_points: int = 20
    min_length_m: float = 500.0
    resample_s: float = 5.0


def haversine_m(a: Point, b: Point) -> float:
    """Great-circle distance between two points in metres."""
    phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
    half_dphi = (phi2 - phi1) / 2
    half_dlmb = math.radians(b.lon - a.lon) / 2
    h = math.sin(half_dphi) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(half_dlmb) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(h))


def clean(traj: RawTrajectory, cfg: CleaningConfig) -> CleanTrajectory | None:
    """Clean one raw trajectory; return ``None`` if it fails the minimum checks.

    Deterministic pipeline: outlier-speed filter, then time-based thinning to at
    least ``resample_s`` between points, then rejection when fewer than
    ``min_points`` points or shorter than ``min_length_m`` remain.
    """
    flags: list[str] = []
    points = _filter_speed(traj.points, cfg.max_speed_kmh, flags)
    points = _resample(points, cfg.resample_s, flags)

    if len(points) < cfg.min_points:
        return None
    length_m = _path_length_m(points)
    if length_m < cfg.min_length_m:
        return None

    duration_s = (points[-1].t - points[0].t).total_seconds()
    return CleanTrajectory(
        traj_id=traj.traj_id,
        user_id=traj.user_id,
        points=points,
        bbox=_bbox(points),
        duration_s=duration_s,
        length_m=length_m,
        mean_speed=length_m / duration_s if duration_s > 0 else 0.0,
        cleaning_flags=tuple(flags),
        split="unassigned",  # assigned once, at CleanTrajectory level, in P3
    )


def _filter_speed(
    points: tuple[Point, ...], max_speed_kmh: float, flags: list[str]
) -> tuple[Point, ...]:
    """Drop points implying a speed above the threshold (or non-increasing time)."""
    if not points:
        return points
    kept = [points[0]]
    for p in points[1:]:
        dt = (p.t - kept[-1].t).total_seconds()
        if dt <= 0:
            continue
        speed_kmh = haversine_m(kept[-1], p) / dt * 3.6
        if speed_kmh > max_speed_kmh:
            continue
        kept.append(p)
    if len(kept) < len(points):
        flags.append(SPEED_FILTERED)
    return tuple(kept)


def _resample(points: tuple[Point, ...], resample_s: float, flags: list[str]) -> tuple[Point, ...]:
    """Thin points so consecutive timestamps are at least ``resample_s`` apart."""
    if not points:
        return points
    kept = [points[0]]
    for p in points[1:]:
        if (p.t - kept[-1].t).total_seconds() >= resample_s:
            kept.append(p)
    if len(kept) < len(points):
        flags.append(RESAMPLED)
    return tuple(kept)


def _path_length_m(points: tuple[Point, ...]) -> float:
    return sum(haversine_m(a, b) for a, b in pairwise(points))


def _bbox(points: tuple[Point, ...]) -> Bbox:
    lons = [p.lon for p in points]
    lats = [p.lat for p in points]
    return (min(lons), min(lats), max(lons), max(lats))

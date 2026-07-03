"""Geolife 1.3 trajectory dataset loader (design doc §2.2, module 2)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from trajguard.datamodel import Point, RawTrajectory
from trajguard.datasets.base import DatasetLoader
from trajguard.experiments.registry import register

_HEADER_LINES = 6
_INVALID_ALTITUDE_FT = -777.0
_FEET_TO_M = 0.3048


@register("dataset", "geolife")
class GeolifeLoader(DatasetLoader):
    """Parses Geolife ``Data/<user_id>/Trajectory/*.plt`` files.

    A ``.plt`` file has 6 header lines followed by one GPS point per line:
    ``lat,lon,0,altitude_ft,serial_date,yyyy-mm-dd,HH:MM:SS`` (WGS84; altitude
    ``-777`` means invalid and is stored as ``None``, otherwise converted to
    metres; timestamps are naive local Beijing time as recorded).
    """

    dataset_id = "geolife"
    native_region = "beijing"

    def __init__(self, root: Path) -> None:
        """``root`` is the directory that contains the Geolife ``Data/`` folder."""
        self.root = root

    def iter_trajectories(self) -> Iterator[RawTrajectory]:
        """Yield raw trajectories in deterministic (user_id, file name) order."""
        for user_dir in sorted((self.root / "Data").iterdir()):
            traj_dir = user_dir / "Trajectory"
            if not traj_dir.is_dir():
                continue
            for plt_file in sorted(traj_dir.glob("*.plt")):
                yield self._parse_file(plt_file, user_id=user_dir.name)

    def _parse_file(self, path: Path, user_id: str) -> RawTrajectory:
        points: list[Point] = []
        with path.open(encoding="utf-8") as fh:
            for lineno, raw_line in enumerate(fh):
                if lineno < _HEADER_LINES:
                    continue
                line = raw_line.strip()
                if not line:
                    continue
                lat, lon, _, alt_ft, _, date, time = line.split(",")
                altitude = float(alt_ft)
                points.append(
                    Point(
                        lat=float(lat),
                        lon=float(lon),
                        t=datetime.fromisoformat(f"{date}T{time}"),
                        alt=None if altitude == _INVALID_ALTITUDE_FT else altitude * _FEET_TO_M,
                    )
                )
        if not points:
            raise ValueError(f"no GPS points in {path}")
        return RawTrajectory(
            traj_id=f"{user_id}_{path.stem}",
            user_id=user_id,
            dataset_id=self.dataset_id,
            points=tuple(points),
            start_t=points[0].t,
            end_t=points[-1].t,
            n_points=len(points),
            source_file=str(path.relative_to(self.root)),
        )

"""Abstract interface for road-network map sources (design doc §2.2, module 1)."""

from abc import ABC, abstractmethod

from trajguard.datamodel import RoadNetwork


class MapSource(ABC):
    """Prepares a road network for a region from OSM or a synthetic source."""

    @property
    @abstractmethod
    def crs(self) -> str:
        """Target coordinate reference system, e.g. ``EPSG:32650``."""

    @abstractmethod
    def load(self) -> RoadNetwork:
        """Build or load the road network for this source."""

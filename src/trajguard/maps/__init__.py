"""Map Manager layer: MapSource interface and the OSMnx-backed implementation."""

from trajguard.maps.base import MapSource
from trajguard.maps.osm import OSMMapSource

__all__ = ["MapSource", "OSMMapSource"]

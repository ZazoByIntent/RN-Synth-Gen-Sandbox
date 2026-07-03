"""Dataset Manager layer: DatasetLoader interface, Geolife loader, and cleaning."""

from trajguard.datasets.base import DatasetLoader
from trajguard.datasets.cleaning import CleaningConfig, clean
from trajguard.datasets.geolife import GeolifeLoader

__all__ = ["CleaningConfig", "DatasetLoader", "GeolifeLoader", "clean"]

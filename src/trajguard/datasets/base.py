"""Abstract interface for trajectory dataset loaders (design doc §2.2, module 2)."""

from abc import ABC, abstractmethod
from collections.abc import Iterator

from trajguard.datamodel import RawTrajectory


class DatasetLoader(ABC):
    """Uniform import of a heterogeneous raw trajectory collection."""

    dataset_id: str
    native_region: str  # e.g. "beijing"; orchestrator validates it against map.region

    @abstractmethod
    def iter_trajectories(self) -> Iterator[RawTrajectory]:
        """Yield raw trajectories parsed from the source files."""

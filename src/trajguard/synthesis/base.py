"""Abstract interface for synthetic trajectory generators (design doc §2.2, module 6)."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from trajguard.datamodel import SyntheticTrajectory, TrajectoryView


class SyntheticGenerator(ABC):
    """Learns a generative model on the train split and samples synthetic paths."""

    @abstractmethod
    def fit(self, train: Sequence[TrajectoryView]) -> None:
        """Fit the generator on the train split only (strict split hygiene for MIA)."""

    @abstractmethod
    def generate(self, n: int, seed: int) -> Sequence[SyntheticTrajectory]:
        """Generate ``n`` synthetic trajectories deterministically from ``seed``."""

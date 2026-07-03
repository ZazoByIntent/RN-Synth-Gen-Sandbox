"""Abstract interface for privacy mechanisms (design doc §2.2, module 5)."""

from abc import ABC, abstractmethod

from trajguard.datamodel import ProtectedTrajectory, TrajectoryView


class PrivacyMechanism(ABC):
    """Protective transformation of a trajectory with privacy-budget accounting."""

    guarantee: str  # "none" | "geo-ind" | "ldp" | "central-dp" | "k-anon"

    @abstractmethod
    def apply(self, traj: TrajectoryView, **params: object) -> ProtectedTrajectory:
        """Apply the mechanism to one trajectory view."""

    @abstractmethod
    def spent_budget(self) -> float | None:
        """Privacy budget spent so far, or ``None`` if the mechanism has none."""

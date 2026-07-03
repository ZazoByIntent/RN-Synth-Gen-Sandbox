"""Abstract interface for evaluation metrics (design doc §2.2, module 8)."""

from abc import ABC, abstractmethod

from trajguard.datamodel import AttackResult


class Metric(ABC):
    """Computes one evaluation metric from an attack result and ground truth."""

    @abstractmethod
    def compute(self, result: AttackResult, ground_truth: object) -> dict[str, float]:
        """Return named metric values for one attack result."""

"""Abstract interface for privacy attacks (design doc §2.2, module 7)."""

from abc import ABC, abstractmethod

from trajguard.datamodel import AttackResult, BackgroundKnowledge


class Attack(ABC):
    """A privacy attack with configurable attacker background knowledge."""

    target_scope: set[str]  # subset of {"raw", "protected", "synthetic"}

    @abstractmethod
    def configure(self, knowledge: BackgroundKnowledge) -> None:
        """Set the attacker's auxiliary knowledge before running."""

    @abstractmethod
    def run(self, target: object, aux: object) -> AttackResult:
        """Execute the attack against the target data."""

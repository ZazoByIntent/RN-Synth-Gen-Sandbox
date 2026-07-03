"""Abstract interface for map matchers (design doc §2.2, module 3)."""

from abc import ABC, abstractmethod

from trajguard.datamodel import CleanTrajectory, MatchedTrajectory, RoadNetwork


class MapMatcher(ABC):
    """Maps GPS points of a cleaned trajectory onto road segments."""

    @abstractmethod
    def match(self, traj: CleanTrajectory, net: RoadNetwork) -> MatchedTrajectory:
        """Match one cleaned trajectory onto the road network."""

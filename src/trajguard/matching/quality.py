"""Match-quality helpers shared by all matchers (design doc §2.2, module 3)."""

from __future__ import annotations

import math

from trajguard.datamodel import MatchedTrajectory

DEFAULT_MIN_MATCH_SCORE = 0.6  # design doc §8


def mean_offset_m(matched: MatchedTrajectory) -> float:
    """Mean GPS-to-road distance in metres (inf when nothing matched)."""
    if not matched.matched_points:
        return math.inf
    return sum(p.offset_m for p in matched.matched_points) / len(matched.matched_points)


def passes_quality(
    matched: MatchedTrajectory, min_match_score: float = DEFAULT_MIN_MATCH_SCORE
) -> bool:
    """Quality gate: trajectories below ``min_match_score`` are discarded."""
    return matched.match_score >= min_match_score

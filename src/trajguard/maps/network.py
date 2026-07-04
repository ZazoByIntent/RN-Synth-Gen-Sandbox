"""Helpers over RoadNetwork artefacts."""

from __future__ import annotations

from trajguard.datamodel import RoadNetwork


def edge_index(net: RoadNetwork) -> dict[tuple[int, int], tuple[int, int]]:
    """Map (u, v) node pairs to (edge_id, key); edge_id is the row position in
    ``net.edges``, stable for a saved artefact.

    HMM matchers identify an edge only by its node pair, so for parallel edges
    (same u, v, different key) the lowest key wins — a documented approximation.
    """
    index: dict[tuple[int, int], tuple[int, int]] = {}
    for edge_id, (u, v, key) in enumerate(net.edges.index):
        if (u, v) not in index or key < index[(u, v)][1]:
            index[(u, v)] = (edge_id, key)
    return index

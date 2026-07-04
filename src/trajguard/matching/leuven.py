"""HMM map matcher backed by leuvenmapmatching (design doc §2.2, module 3)."""

from __future__ import annotations

import logging

from leuvenmapmatching.map.inmem import InMemMap
from leuvenmapmatching.matcher.distance import DistanceMatcher
from pyproj import Transformer

from trajguard.datamodel import CleanTrajectory, MatchedPoint, MatchedTrajectory, RoadNetwork
from trajguard.experiments.registry import register
from trajguard.maps.network import edge_index
from trajguard.matching.base import MapMatcher

_LEUVEN_LOGGER = "be.kuleuven.cs.dtai.mapmatching"
_WGS84 = "EPSG:4326"


@register("matcher", "leuven")
class LeuvenMapMatcher(MapMatcher):
    """Pure-Python HMM matcher — chosen over fmm for calibration because it is
    easy to debug; fmm can slot in behind the same ABC later.

    ``match_score = frac_matched * (1 - min(1, mean_offset_m / max_dist))``,
    a [0, 1] score combining coverage and geometric fit. Parameter defaults were
    calibrated on the Geolife fixture (P2): looser than the library's documented
    city-driving values because Geolife mixes walking/cycling with GPS warm-up
    drift at track starts (max_dist_init) and off-street segments (obs_noise).
    """

    def __init__(
        self,
        max_dist: float = 150.0,
        max_dist_init: float = 100.0,
        min_prob_norm: float = 0.001,
        obs_noise: float = 75.0,
        obs_noise_ne: float = 100.0,
        dist_noise: float = 75.0,
        non_emitting_states: bool = True,
        max_lattice_width: int = 5,
    ) -> None:
        """Store matcher parameters; the road network arrives per match() call."""
        self.max_dist = max_dist
        self.max_dist_init = max_dist_init
        self.min_prob_norm = min_prob_norm
        self.obs_noise = obs_noise
        self.obs_noise_ne = obs_noise_ne
        self.dist_noise = dist_noise
        self.non_emitting_states = non_emitting_states
        self.max_lattice_width = max_lattice_width
        self._map_cache: tuple[int, InMemMap] | None = None  # keyed by id(net)
        logging.getLogger(_LEUVEN_LOGGER).setLevel(logging.WARNING)

    def match(self, traj: CleanTrajectory, net: RoadNetwork) -> MatchedTrajectory:
        """Match one cleaned trajectory; never drops — see ``passes_quality``.

        A failed or partial match is expressed through ``frac_matched`` and
        ``match_score`` (0.0 when nothing matched), not by raising.
        """
        transformer = Transformer.from_crs(_WGS84, net.crs, always_xy=True)
        path = [transformer.transform(p.lon, p.lat) for p in traj.points]  # (x, y)

        matcher = DistanceMatcher(
            self._map_for(net),
            max_dist=self.max_dist,
            max_dist_init=self.max_dist_init,
            min_prob_norm=self.min_prob_norm,
            obs_noise=self.obs_noise,
            obs_noise_ne=self.obs_noise_ne,
            dist_noise=self.dist_noise,
            non_emitting_states=self.non_emitting_states,
            max_lattice_width=self.max_lattice_width,
        )
        _, last_idx = matcher.match(path)

        eindex = edge_index(net)
        matched_points: list[MatchedPoint] = []
        edge_ids: list[int] = []
        prev_pair: tuple[int, int] | None = None
        for state in matcher.lattice_best:
            if state.obs_ne != 0:  # non-emitting: interpolated, no GPS point behind it
                pair = (state.edge_m.l1, state.edge_m.l2)
            else:
                x, y = state.edge_m.pi  # leuven's projection of the obs onto the edge
                matched_points.append(
                    MatchedPoint(x=x, y=y, t=traj.points[state.obs].t, offset_m=state.dist_obs)
                )
                pair = (state.edge_m.l1, state.edge_m.l2)
            if pair != prev_pair:
                found = eindex.get(pair)
                if found is not None:
                    edge_ids.append(found[0])
                prev_pair = pair

        n_points = len(traj.points)
        frac_matched = (last_idx + 1) / n_points if n_points and matched_points else 0.0
        if matched_points:
            mean_offset = sum(p.offset_m for p in matched_points) / len(matched_points)
            score = frac_matched * (1.0 - min(1.0, mean_offset / self.max_dist))
        else:
            score = 0.0
        return MatchedTrajectory(
            traj_id=traj.traj_id,
            user_id=traj.user_id,
            map_id=net.region,  # Map entity ids arrive with the orchestrator (P4)
            edge_seq=tuple(edge_ids),
            matched_points=tuple(matched_points),
            match_score=score,
            frac_matched=frac_matched,
        )

    def _map_for(self, net: RoadNetwork) -> InMemMap:
        """Build (or reuse) the leuven in-memory map for a network."""
        if self._map_cache is not None and self._map_cache[0] == id(net):
            return self._map_cache[1]
        map_con = InMemMap("trajguard", use_latlon=False)
        for node_id, row in net.nodes.iterrows():
            map_con.add_node(node_id, (row["x"], row["y"]))  # (x, y): same order as path
        for u, v, _key in net.edges.index:
            map_con.add_edge(u, v)  # OSMnx rows are directional; one-ways stay one-way
        map_con.purge()
        self._map_cache = (id(net), map_con)
        return map_con

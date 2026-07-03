"""OSM road-network source via OSMnx (design doc §2.2, module 1)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from osmnx import convert, graph, io, projection

from trajguard.datamodel import Bbox, RoadNetwork
from trajguard.experiments.registry import register
from trajguard.maps.base import MapSource

if TYPE_CHECKING:
    import geopandas as gpd
    import networkx as nx


@register("map_source", "osm")
class OSMMapSource(MapSource):
    """Downloads an OSM road network for a bbox, or loads it from the local cache.

    The GraphML file is the canonical artefact; the node/edge Parquet tables are
    a query-friendly sidecar (DuckDB later). ``bbox`` is ``(west, south, east,
    north)`` in EPSG:4326 — the OSMnx v2 order.
    """

    def __init__(
        self,
        region: str,
        bbox: Bbox,
        crs: str,
        network_type: str = "drive",
        maps_dir: Path = Path("maps"),
    ) -> None:
        """Configure a source for one region; nothing is downloaded until load()."""
        self.region = region
        self.bbox = bbox
        self._crs = crs
        self.network_type = network_type
        self.maps_dir = maps_dir

    @property
    def crs(self) -> str:
        """Target projected CRS, e.g. ``EPSG:32650`` for Beijing."""
        return self._crs

    @property
    def graphml_path(self) -> Path:
        """Location of the cached GraphML artefact for this region."""
        return self.maps_dir / self.region / "graph.graphml"

    def load(self) -> RoadNetwork:
        """Load the cached network, downloading and saving it first if absent."""
        if self.graphml_path.exists():
            g = io.load_graphml(self.graphml_path)
        else:
            g = self._download()
            self.save(g)
        nodes, edges = convert.graph_to_gdfs(g)
        return RoadNetwork(graph=g, nodes=nodes, edges=edges, crs=self._crs, region=self.region)

    def save(self, g: nx.MultiDiGraph[int]) -> None:
        """Persist a projected graph as GraphML plus node/edge Parquet tables."""
        self.graphml_path.parent.mkdir(parents=True, exist_ok=True)
        io.save_graphml(g, self.graphml_path)
        nodes, edges = convert.graph_to_gdfs(g)
        _to_parquet(nodes, self.graphml_path.parent / "nodes.parquet")
        _to_parquet(edges, self.graphml_path.parent / "edges.parquet")

    def _download(self) -> nx.MultiDiGraph[int]:
        g = graph.graph_from_bbox(self.bbox, network_type=self.network_type)
        return projection.project_graph(g, to_crs=self._crs)


def _to_parquet(gdf: gpd.GeoDataFrame, path: Path) -> None:
    """Write a GeoDataFrame to Parquet, stringifying mixed-type object columns.

    OSM attributes like ``osmid`` or ``highway`` can mix scalars and lists after
    simplification, which pyarrow rejects; GraphML remains the lossless artefact.
    """
    out = gdf.copy()
    for col in out.columns:
        if col != "geometry" and out[col].dtype == object:
            out[col] = out[col].astype(str)
    out.to_parquet(path)

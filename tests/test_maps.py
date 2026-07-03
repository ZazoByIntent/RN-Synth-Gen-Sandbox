"""Tests for OSMMapSource load/save against the committed Beijing slice."""

import json
from pathlib import Path

import pytest

from trajguard.experiments import registry
from trajguard.maps import OSMMapSource

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_MAPS = FIXTURES / "maps"
MANIFEST = json.loads((FIXTURES / "geolife" / "MANIFEST.json").read_text(encoding="utf-8"))
AREA = tuple(MANIFEST["area_west_south_east_north"])  # single source of truth


def _source(maps_dir: Path) -> OSMMapSource:
    return OSMMapSource(region="beijing", bbox=AREA, crs="EPSG:32650", maps_dir=maps_dir)


def test_registered_in_registry() -> None:
    assert registry.get("map_source", "osm") is OSMMapSource


def test_load_from_cache_without_network() -> None:
    net = _source(FIXTURE_MAPS).load()
    assert net.crs == "EPSG:32650"
    assert net.region == "beijing"
    assert len(net.nodes) > 0 and len(net.edges) > 0
    assert net.graph.number_of_nodes() == len(net.nodes)
    assert net.graph.number_of_edges() == len(net.edges)
    assert net.graph.graph["crs"] is not None


def test_save_and_reload_round_trip(tmp_path: Path) -> None:
    net = _source(FIXTURE_MAPS).load()
    target = _source(tmp_path)
    target.save(net.graph)
    region_dir = tmp_path / "beijing"
    for artefact in ("graph.graphml", "nodes.parquet", "edges.parquet"):
        assert (region_dir / artefact).exists()

    reloaded = target.load()  # hits the freshly written cache
    assert reloaded.graph.number_of_nodes() == net.graph.number_of_nodes()
    assert reloaded.graph.number_of_edges() == net.graph.number_of_edges()
    assert len(reloaded.nodes) == len(net.nodes)
    assert len(reloaded.edges) == len(net.edges)


def test_load_rejects_cached_graph_with_wrong_crs(tmp_path: Path) -> None:
    net = _source(FIXTURE_MAPS).load()
    mislabelled = net.graph.copy()
    mislabelled.graph["crs"] = "EPSG:4326"
    target = _source(tmp_path)
    target.save(mislabelled)
    with pytest.raises(ValueError, match="CRS"):
        target.load()

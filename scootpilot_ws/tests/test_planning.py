import pathlib

import pytest

pytest.importorskip('numpy')

from scootpilot_planning.osm_loader import WHITELIST, load_osm

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_osm_whitelist_only():
    osm = load_osm(str(ROOT / 'config/map/area.osm.pbf'), whitelist=WHITELIST)
    for _, _, data in osm.graph.edges(data=True):
        assert data['weight'] > 0


def test_path_continuity():
    osm = load_osm(str(ROOT / 'config/map/area.osm.pbf'))
    nodes = list(osm.nodes.values())
    path = osm.shortest_path(nodes[0], nodes[-1])
    assert len(path) >= 2

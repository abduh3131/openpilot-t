from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import networkx as nx


WHITELIST = {'footway', 'path', 'cycleway', 'sidewalk', 'shoulder'}


@dataclass
class OSMMap:
    graph: nx.Graph
    nodes: Dict[int, Tuple[float, float]]

    def shortest_path(self, start: Tuple[float, float], goal: Tuple[float, float]) -> List[int]:
        start_node = min(self.nodes, key=lambda nid: _haversine(self.nodes[nid], start))
        goal_node = min(self.nodes, key=lambda nid: _haversine(self.nodes[nid], goal))
        return nx.shortest_path(self.graph, start_node, goal_node, weight='weight')


def load_osm(path: str, whitelist: Iterable[str] | None = None) -> OSMMap:
    allowed = set(whitelist or WHITELIST)
    osm_path = Path(path)
    tree = ET.parse(osm_path)
    root = tree.getroot()
    nodes: Dict[int, Tuple[float, float]] = {}
    graph = nx.Graph()
    for node in root.findall('node'):
        nid = int(node.attrib['id'])
        lat = float(node.attrib['lat'])
        lon = float(node.attrib['lon'])
        nodes[nid] = (lat, lon)
        graph.add_node(nid)
    for way in root.findall('way'):
        tags = {tag.attrib['k']: tag.attrib['v'] for tag in way.findall('tag')}
        if tags.get('highway') not in allowed:
            continue
        nds = [int(nd.attrib['ref']) for nd in way.findall('nd')]
        for a, b in zip(nds[:-1], nds[1:]):
            if a not in nodes or b not in nodes:
                continue
            dist = _haversine(nodes[a], nodes[b])
            graph.add_edge(a, b, weight=dist)
    return OSMMap(graph=graph, nodes=nodes)


def _haversine(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2 * r * math.asin(math.sqrt(h))


__all__ = ['load_osm', 'OSMMap']

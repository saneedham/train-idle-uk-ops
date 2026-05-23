"""Graph and routing utilities (direction-aware).

PR 3: extracted from train_idle_monolith.py.
"""

from __future__ import annotations

import heapq

from train_idle.models import GameState


def build_active_adjacency(world, state: GameState) -> dict[str, list[tuple[str, str, float]]]:
    """Build adjacency list from discovered edges, respecting bidirectional flags."""
    adj: dict[str, list[tuple[str, str, float]]] = {}
    for eid in set(state.discovered_edges):
        e = world.edges.get(eid)
        if not e:
            continue
        adj.setdefault(e.a, []).append((e.b, eid, e.km))
        if e.bidir:
            adj.setdefault(e.b, []).append((e.a, eid, e.km))
    return adj


def dijkstra_path(
    adj: dict[str, list[tuple[str, str, float]]], start: str, goal: str
) -> tuple[list[str], list[str], float]:
    """Return (node_path, edge_path, distance_km)."""
    if start == goal:
        return [start], [], 0.0

    dist: dict[str, float] = {start: 0.0}
    prev: dict[str, tuple[str, str]] = {}
    pq: list[tuple[float, str]] = [(0.0, start)]

    while pq:
        d, u = heapq.heappop(pq)
        if u == goal:
            break
        if d != dist.get(u, float('inf')):
            continue
        for v, eid, km in adj.get(u, []):
            nd = d + km
            if nd < dist.get(v, float('inf')):
                dist[v] = nd
                prev[v] = (u, eid)
                heapq.heappush(pq, (nd, v))

    if goal not in dist:
        return [start], [], float('inf')

    nodes = [goal]
    edges: list[str] = []
    cur = goal
    while cur != start:
        p, eid = prev[cur]
        edges.append(eid)
        nodes.append(p)
        cur = p
    nodes.reverse()
    edges.reverse()
    return nodes, edges, dist[goal]

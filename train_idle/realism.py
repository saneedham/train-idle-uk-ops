"""Realism Overrides (track counts, speed limits, directionality).

PR 3: extracted from train_idle_monolith.py.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

REALISM_DIR = 'realism'


@dataclass
class RealismInfo:
    path: str = ''
    loaded: bool = False
    edge_overrides: dict[str, dict] = field(default_factory=dict)


def realism_path_for(region_id: str) -> str:
    # e.g. realism/devon.json
    return os.path.join(REALISM_DIR, f'{region_id}.json')


def load_realism_overrides(region_id: str) -> RealismInfo:
    os.makedirs(REALISM_DIR, exist_ok=True)
    path = realism_path_for(region_id)

    # If missing: create an empty scaffold (devon may later be seeded differently)
    if not os.path.exists(path):
        scaffold = {
            'meta': {'region_id': region_id, 'notes': ['Fill edges with overrides.']},
            'edges': {},
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(scaffold, f, indent=2)

    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        edge_overrides = dict(data.get('edges', {}))
        return RealismInfo(path=path, loaded=True, edge_overrides=edge_overrides)
    except Exception:
        return RealismInfo(path=path, loaded=False, edge_overrides={})


def apply_realism_overrides_to_world(world, realism: RealismInfo) -> int:
    """Apply overrides to world.edges. Returns count applied."""
    applied = 0
    for eid, ov in (realism.edge_overrides or {}).items():
        e = world.edges.get(eid)
        if not e:
            continue

        changed = False
        if 'tracks' in ov and ov['tracks'] is not None:
            e.tracks = int(ov['tracks'])
            changed = True
        if 'bidir' in ov and ov['bidir'] is not None:
            e.bidir = bool(ov['bidir'])
            changed = True
        if 'speed_kmh' in ov and ov['speed_kmh'] is not None:
            e.speed_kmh = float(ov['speed_kmh'])
            changed = True

        if changed:
            applied += 1
    return applied

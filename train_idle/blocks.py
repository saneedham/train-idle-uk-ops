"""Track block occupancy and signalling abstractions.

PR4A: extracted from train_idle_monolith.py.
"""

from __future__ import annotations

from train_idle.models import Edge, GameState


def make_block_for_edge(e: Edge) -> dict:
    """Create a block occupancy structure for an edge based on track count."""
    return {'mode': 'single', 'occ': None} if e.tracks <= 1 else {'mode': 'dir', 'occ_fwd': None, 'occ_rev': None}


def rebuild_blocks(world, state: GameState, blocks: dict[str, dict]) -> None:
    """Rebuild blocks for discovered edges, respecting current tracks in world.edges."""
    blocks.clear()
    for eid in state.discovered_edges:
        e = world.edges.get(eid)
        if e:
            blocks[eid] = make_block_for_edge(e)


def block_is_free(block: dict, dir_sign: int) -> bool:
    """Return True if the block is free in the requested direction."""
    if block['mode'] == 'single':
        return block['occ'] is None
    return (block['occ_fwd'] is None) if dir_sign > 0 else (block['occ_rev'] is None)


def block_reserve(block: dict, tid: int, dir_sign: int) -> None:
    """Reserve occupancy in the block for a train id in a direction."""
    if block['mode'] == 'single':
        block['occ'] = tid
    else:
        if dir_sign > 0:
            block['occ_fwd'] = tid
        else:
            block['occ_rev'] = tid


def block_release(block: dict, tid: int) -> None:
    """Release any occupancy held by the given train id."""
    if block['mode'] == 'single':
        if block.get('occ') == tid:
            block['occ'] = None
    else:
        if block.get('occ_fwd') == tid:
            block['occ_fwd'] = None
        if block.get('occ_rev') == tid:
            block['occ_rev'] = None

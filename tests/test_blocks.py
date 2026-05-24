from train_idle.blocks import block_is_free, block_release, block_reserve, make_block_for_edge
from train_idle.models import Edge


def test_single_track_block_occupancy():
    e = Edge(id='E1', a='A', b='B', km=1.0, tracks=1, bidir=True)
    block = make_block_for_edge(e)

    assert block['mode'] == 'single'
    assert block_is_free(block, dir_sign=1)

    block_reserve(block, tid=7, dir_sign=1)
    assert not block_is_free(block, dir_sign=1)

    block_release(block, tid=7)
    assert block_is_free(block, dir_sign=-1)


def test_double_track_directional_occupancy():
    e = Edge(id='E2', a='A', b='B', km=1.0, tracks=2, bidir=True)
    block = make_block_for_edge(e)

    assert block['mode'] == 'dir'
    assert block_is_free(block, dir_sign=1)
    assert block_is_free(block, dir_sign=-1)

    block_reserve(block, tid=1, dir_sign=1)
    assert not block_is_free(block, dir_sign=1)
    assert block_is_free(block, dir_sign=-1)

    block_release(block, tid=1)
    assert block_is_free(block, dir_sign=1)

import math

from train_idle.graph import dijkstra_path


def test_dijkstra_trivial():
    adj = {'A': [('B', 'E_AB', 5.0)], 'B': [('A', 'E_AB', 5.0)]}
    nodes, edges, dist = dijkstra_path(adj, 'A', 'B')
    assert nodes == ['A', 'B']
    assert edges == ['E_AB']
    assert math.isclose(dist, 5.0)

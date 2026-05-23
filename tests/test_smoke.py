import importlib
import math


def test_module_imports():
    # Import should not trigger curses UI (must be guarded by `if __name__ == "__main__":`)
    importlib.import_module('train_idle')


def test_dijkstra_trivial():
    train_idle = importlib.import_module('train_idle')

    adj = {'A': [('B', 'E_AB', 5.0)], 'B': [('A', 'E_AB', 5.0)]}
    nodes, edges, dist = train_idle.dijkstra_path(adj, 'A', 'B')
    assert nodes == ['A', 'B']
    assert edges == ['E_AB']
    assert math.isclose(dist, 5.0)

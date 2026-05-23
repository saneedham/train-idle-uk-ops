"""Train Idle: UK Ops package.

PR 1: Package shell.
For now we keep the game logic in train_idle_monolith.py and re-export a small
public surface so existing imports/tests remain stable.
"""

from train_idle_monolith import dijkstra_path, main

__all__ = ['dijkstra_path', 'main']

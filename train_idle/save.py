"""Save/load helpers for Train Idle: UK Ops.

PR4B: extracted from train_idle_monolith.py.

Design goals:
- Keep default save behaviour unchanged.
- Allow tests to use a temporary path (no real files touched).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict

from train_idle.models import GameState, Train

DEFAULT_SAVE_FILE = 'train_idle_save_v05661.json'
DEFAULT_REGION_ID = 'devon'


def save_game(state: GameState, path: str = DEFAULT_SAVE_FILE) -> None:
    """Persist game state to JSON."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(asdict(state), f, indent=2)


def load_game(path: str = DEFAULT_SAVE_FILE) -> GameState | None:
    """Load game state from JSON, if present."""
    if not os.path.exists(path):
        return None

    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    return GameState(
        money=float(data.get('money', 300.0)),
        home=data.get('home'),
        trains=[Train(**t) for t in data.get('trains', [])],
        next_train_id=int(data.get('next_train_id', 1)),
        game_time=float(data.get('game_time', 0.0)),
        time_scale=float(data.get('time_scale', 60.0)),
        paused=bool(data.get('paused', False)),
        last_real_time=float(data.get('last_real_time', time.time())),
        region_ids_loaded=list(data.get('region_ids_loaded', [DEFAULT_REGION_ID])),
        discovered_nodes=list(data.get('discovered_nodes', [])),
        discovered_edges=list(data.get('discovered_edges', [])),
        last_unlock_options=dict(data.get('last_unlock_options', {})),
        msg_log=list(data.get('msg_log', [])),
        ui_show_map=bool(data.get('ui_show_map', True)),
        verbose=bool(data.get('verbose', False)),
        pinned_override_lines=list(data.get('pinned_override_lines', [])),
        pinned_override_until_game=float(data.get('pinned_override_until_game', 0.0)),
        cmd_history=list(data.get('cmd_history', [])),
        cmd_hist_idx=int(data.get('cmd_hist_idx', -1)),
        svc_last_complete=dict(data.get('svc_last_complete', {})),
        svc_ontime_flags=dict(data.get('svc_ontime_flags', {})),
        svc_headway_hist_s=dict(data.get('svc_headway_hist_s', {})),
        view_cx=float(data.get('view_cx', 52.0)),
        view_cy=float(data.get('view_cy', 10.0)),
        view_zoom=float(data.get('view_zoom', 1.0)),
        follow_train_id=data.get('follow_train_id', None),
        color_enabled=bool(data.get('color_enabled', True)),
        theme_flavor=str(data.get('theme_flavor', 'mocha')),
    )


def new_game(default_region_id: str = DEFAULT_REGION_ID) -> GameState:
    """Create a brand-new game state."""
    st = GameState()
    st.trains.append(Train(id=0, model_id='dmu'))
    st.next_train_id = 1

    # Keep configuration defaults in the "app layer" rather than the dataclass defaults.
    st.region_ids_loaded = [default_region_id]

    # Note: log_event lives in the monolith for now; PR4C/PR5 can relocate logging later.
    return st

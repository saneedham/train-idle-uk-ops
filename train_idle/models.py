"""Core dataclasses for Train Idle: UK Ops.

PR 2: extracted from train_idle_monolith.py to make the codebase modular and testable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

# -----------------------------
# Data models
# -----------------------------


@dataclass
class Node:
    id: str
    name: str
    kind: str
    size: int = 1
    major: bool = False


@dataclass
class Edge:
    id: str
    a: str
    b: str
    km: float
    speed_kmh: float = 120.0
    tracks: int = 1
    bidir: bool = True


@dataclass
class TrainModel:
    id: str
    name: str
    kind: str
    cost: int
    cruise_kmh: float
    capacity: int


@dataclass
class ServiceTemplate:
    id: str
    name: str
    kind: str
    pattern: str
    calls: list[str]
    fare_per_km: float = 0.09
    rate_per_ton_km: float = 0.055
    target_headway_s: int = 3600
    grace_pct: float = 0.10


@dataclass
class Service:
    id: str
    name: str
    kind: str
    pattern: str
    calls: list[str]
    dwell_minor_s: int = 25
    dwell_major_s: int = 40
    turnaround_s: int = 60
    fare_per_km: float = 0.09
    express_premium: float = 1.35
    local_coverage: float = 1.20
    express_coverage: float = 0.85
    rate_per_ton_km: float = 0.055
    target_headway_s: int = 3600
    grace_pct: float = 0.10


@dataclass
class Train:
    id: int
    model_id: str
    service_id: str | None = None
    state: str = 'IDLE'
    at_node: str | None = None
    call_index: int = 0
    direction: int = 1
    path_nodes: list[str] = field(default_factory=list)
    path_edges: list[str] = field(default_factory=list)
    current_edge: str | None = None
    edge_depart_t: float = 0.0
    edge_arrive_t: float = 0.0
    next_event_t: float = 0.0
    last_revenue: float = 0.0
    last_task: str = ''


@dataclass
class GameState:
    money: float = 300.0
    home: str | None = None
    trains: list[Train] = field(default_factory=list)
    next_train_id: int = 1

    game_time: float = 0.0
    time_scale: float = 60.0
    paused: bool = False
    last_real_time: float = field(default_factory=lambda: time.time())

    region_ids_loaded: list[str] = field(default_factory=list)
    discovered_nodes: list[str] = field(default_factory=list)
    discovered_edges: list[str] = field(default_factory=list)
    last_unlock_options: dict[str, str] = field(default_factory=dict)

    msg_log: list[str] = field(default_factory=list)
    ui_show_map: bool = True
    verbose: bool = False

    pinned_override_lines: list[str] = field(default_factory=list)
    pinned_override_until_game: float = 0.0

    cmd_history: list[str] = field(default_factory=list)
    cmd_hist_idx: int = -1

    svc_last_complete: dict[str, float] = field(default_factory=dict)
    svc_ontime_flags: dict[str, list[int]] = field(default_factory=dict)
    svc_headway_hist_s: dict[str, list[float]] = field(default_factory=dict)

    view_cx: float = 52.0
    view_cy: float = 10.0
    view_zoom: float = 1.0
    follow_train_id: int | None = None

    color_enabled: bool = True
    theme_flavor: str = 'mocha'

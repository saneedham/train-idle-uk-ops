#!/usr/bin/env python3
"""Train Idle: UK Ops (v0.5.6.6.1) — Real-world Track Overrides + Track Realism + Headways B

New in v0.5.6.6.1
- Real-world track data overrides:
  * Loads per-region overrides from realism/<region>.json (default: realism/devon.json).
  * Overrides can set: tracks, bidir, speed_kmh (per edge id).
  * Applied at world load (affects routing, signalling blocks, costs, and map rendering).
  * Includes commands:
      realism           Show loaded override file + count
      realism reload    Reload overrides from disk (rebuilds blocks for discovered edges)

Existing features retained
- Track realism: single vs multi track occupancy, bidir enforcement for movement & pathfinding.
- Map visuals: '-' single track, '=' double/multi, '#' occupied.
- Canonical dog-leg geometry per diagonal edge; train marker follows branch both directions.
- Junction derived 3-char codes: EXD_W->XDW, TAU_W->TUW, YEO_JN->YJN.
- Headways Option B: per-service + network headway health.
- Catppuccin themes + header KPI placement fix.

Run:
  python3 train_idle_v0566.py
Save:
  train_idle_save_v05661.json
"""

import curses
import heapq
import json
import math
import os
import shlex
import time
from dataclasses import asdict, dataclass, field

SAVE_FILE = 'train_idle_save_v05661.json'
REGION_DIR = 'regions'
REALISM_DIR = 'realism'
DEFAULT_REGION_ID = 'devon'

# -----------------------------
# Catppuccin palettes (hex)
# -----------------------------

CATPPUCCIN = {
    'latte': {
        'rosewater': '#dc8a78',
        'flamingo': '#dd7878',
        'pink': '#ea76cb',
        'mauve': '#8839ef',
        'red': '#d20f39',
        'maroon': '#e64553',
        'peach': '#fe640b',
        'yellow': '#df8e1d',
        'green': '#40a02b',
        'teal': '#179299',
        'sky': '#04a5e5',
        'sapphire': '#209fb5',
        'blue': '#1e66f5',
        'lavender': '#7287fd',
        'text': '#4c4f69',
        'subtext1': '#5c5f77',
        'subtext0': '#6c6f85',
        'overlay2': '#7c7f93',
        'overlay1': '#8c8fa1',
        'overlay0': '#9ca0b0',
        'surface2': '#acb0be',
        'surface1': '#bcc0cc',
        'surface0': '#ccd0da',
        'base': '#eff1f5',
        'mantle': '#e6e9ef',
        'crust': '#dce0e8',
    },
    'frappe': {
        'rosewater': '#f2d5cf',
        'flamingo': '#eebebe',
        'pink': '#f4b8e4',
        'mauve': '#ca9ee6',
        'red': '#e78284',
        'maroon': '#ea999c',
        'peach': '#ef9f76',
        'yellow': '#e5c890',
        'green': '#a6d189',
        'teal': '#81c8be',
        'sky': '#99d1db',
        'sapphire': '#85c1dc',
        'blue': '#8caaee',
        'lavender': '#babbf1',
        'text': '#c6d0f5',
        'subtext1': '#b5bfe2',
        'subtext0': '#a5adce',
        'overlay2': '#949cbb',
        'overlay1': '#838ba7',
        'overlay0': '#737994',
        'surface2': '#626880',
        'surface1': '#51576d',
        'surface0': '#414559',
        'base': '#303446',
        'mantle': '#292c3c',
        'crust': '#232634',
    },
    'macchiato': {
        'rosewater': '#f4dbd6',
        'flamingo': '#f0c6c6',
        'pink': '#f5bde6',
        'mauve': '#c6a0f6',
        'red': '#ed8796',
        'maroon': '#ee99a0',
        'peach': '#f5a97f',
        'yellow': '#eed49f',
        'green': '#a6da95',
        'teal': '#8bd5ca',
        'sky': '#91d7e3',
        'sapphire': '#7dc4e4',
        'blue': '#8aadf4',
        'lavender': '#b7bdf8',
        'text': '#cad3f5',
        'subtext1': '#b8c0e0',
        'subtext0': '#a5adcb',
        'overlay2': '#939ab7',
        'overlay1': '#8087a2',
        'overlay0': '#6e738d',
        'surface2': '#5b6078',
        'surface1': '#494d64',
        'surface0': '#363a4f',
        'base': '#24273a',
        'mantle': '#1e2030',
        'crust': '#181926',
    },
    'mocha': {
        'rosewater': '#f5e0dc',
        'flamingo': '#f2cdcd',
        'pink': '#f5c2e7',
        'mauve': '#cba6f7',
        'red': '#f38ba8',
        'maroon': '#eba0ac',
        'peach': '#fab387',
        'yellow': '#f9e2af',
        'green': '#a6e3a1',
        'teal': '#94e2d5',
        'sky': '#89dceb',
        'sapphire': '#74c7ec',
        'blue': '#89b4fa',
        'lavender': '#b4befe',
        'text': '#cdd6f4',
        'subtext1': '#bac2de',
        'subtext0': '#a6adc8',
        'overlay2': '#9399b2',
        'overlay1': '#7f849c',
        'overlay0': '#6c7086',
        'surface2': '#585b70',
        'surface1': '#45475a',
        'surface0': '#313244',
        'base': '#1e1e2e',
        'mantle': '#181825',
        'crust': '#11111b',
    },
}

# -----------------------------
# Curses-safe helpers
# -----------------------------


def safe_addstr(win, y: int, x: int, s: str, attr: int = 0) -> None:
    try:
        win.addstr(y, x, s, attr) if attr else win.addstr(y, x, s)
    except curses.error:
        pass


def safe_addch(win, y: int, x: int, ch, attr: int = 0) -> None:
    try:
        win.addch(y, x, ch, attr) if attr else win.addch(y, x, ch)
    except curses.error:
        pass


def init_curses(stdscr) -> None:
    try:
        curses.start_color()
        curses.use_default_colors()
        stdscr.bkgd(' ', curses.color_pair(0))
    except curses.error:
        return


def apply_win_bkgd(win) -> None:
    try:
        win.bkgd(' ', curses.color_pair(0))
    except curses.error:
        pass


# -----------------------------
# Colour system (roles)
# -----------------------------

ROLE = {
    'TITLE': 1,
    'HEADER': 2,
    'DIM': 3,
    'GOOD': 4,
    'OK': 5,
    'WARN': 6,
    'BAD': 7,
    'RUN': 8,
    'WAIT': 9,
    'DWELL': 10,
    'IDLE': 11,
    'TRACK': 12,
    'TRACK_OCC': 13,
    'JUNCTION': 14,
    'STATION_MAJOR': 15,
    'STATION_MINOR': 16,
}


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip('#')
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _xterm_256_palette() -> list[tuple[int, int, int]]:
    base = [
        (0, 0, 0),
        (205, 0, 0),
        (0, 205, 0),
        (205, 205, 0),
        (0, 0, 238),
        (205, 0, 205),
        (0, 205, 205),
        (229, 229, 229),
        (127, 127, 127),
        (255, 0, 0),
        (0, 255, 0),
        (255, 255, 0),
        (92, 92, 255),
        (255, 0, 255),
        (0, 255, 255),
        (255, 255, 255),
    ]
    steps = [0, 95, 135, 175, 215, 255]
    cube = [(r, g, b) for r in steps for g in steps for b in steps]
    gray = [(i, i, i) for i in range(8, 239, 10)]
    return base + cube + gray


def _nearest_xterm_index(rgb: tuple[int, int, int]) -> int:
    pal = _xterm_256_palette()
    r, g, b = rgb
    best_i, best_d = 0, 10**18
    for i, (pr, pg, pb) in enumerate(pal):
        dr, dg, db = r - pr, g - pg, b - pb
        d = dr * dr + dg * dg + db * db
        if d < best_d:
            best_d = d
            best_i = i
    return best_i


def _init_pair_safe(pair_id: int, fg: int) -> None:
    try:
        curses.init_pair(pair_id, fg, -1)
    except curses.error:
        pass


def init_theme_colors(state) -> None:
    if not curses.has_colors():
        return
    flav = getattr(state, 'theme_flavor', 'mocha') or 'mocha'
    flav = flav.lower()
    if flav not in CATPPUCCIN:
        flav = 'mocha'
    p = CATPPUCCIN[flav]
    use_256 = getattr(curses, 'COLORS', 0) >= 256

    def fg(name: str, fallback: int) -> int:
        if not use_256:
            return fallback
        return _nearest_xterm_index(_hex_to_rgb(p[name]))

    _init_pair_safe(ROLE['TITLE'], fg('mauve', curses.COLOR_MAGENTA))
    _init_pair_safe(ROLE['HEADER'], fg('text', curses.COLOR_WHITE))
    _init_pair_safe(ROLE['DIM'], fg('overlay0', curses.COLOR_BLACK))
    _init_pair_safe(ROLE['GOOD'], fg('green', curses.COLOR_GREEN))
    _init_pair_safe(ROLE['OK'], fg('teal', curses.COLOR_CYAN))
    _init_pair_safe(ROLE['WARN'], fg('yellow', curses.COLOR_YELLOW))
    _init_pair_safe(ROLE['BAD'], fg('red', curses.COLOR_RED))
    _init_pair_safe(ROLE['RUN'], fg('green', curses.COLOR_GREEN))
    _init_pair_safe(ROLE['WAIT'], fg('yellow', curses.COLOR_YELLOW))
    _init_pair_safe(ROLE['DWELL'], fg('blue', curses.COLOR_BLUE))
    _init_pair_safe(ROLE['IDLE'], fg('overlay1', curses.COLOR_WHITE))
    _init_pair_safe(ROLE['TRACK'], fg('surface2', curses.COLOR_WHITE))
    _init_pair_safe(ROLE['TRACK_OCC'], fg('peach', curses.COLOR_YELLOW))
    _init_pair_safe(ROLE['JUNCTION'], fg('mauve', curses.COLOR_MAGENTA))
    _init_pair_safe(ROLE['STATION_MAJOR'], fg('text', curses.COLOR_WHITE))
    _init_pair_safe(ROLE['STATION_MINOR'], fg('subtext0', curses.COLOR_WHITE))


def attr_for(state, role: str, bold: bool = False) -> int:
    if not getattr(state, 'color_enabled', True):
        return curses.A_BOLD if bold else 0
    if not curses.has_colors():
        return curses.A_BOLD if bold else 0
    a = curses.color_pair(ROLE.get(role, 0))
    if bold:
        a |= curses.A_BOLD
    return a


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

    region_ids_loaded: list[str] = field(default_factory=lambda: [DEFAULT_REGION_ID])
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


# -----------------------------
# Devon bundle + map coords
# -----------------------------

DEVON_BUNDLE = {
    'region_id': 'devon',
    'version': 'v056-scopeAplus',
    'nodes': [
        {'id': 'PLY', 'name': 'Plymouth', 'kind': 'STATION', 'size': 4, 'major': True},
        {'id': 'NWP', 'name': 'Newton Abbot', 'kind': 'STATION', 'size': 3, 'major': False},
        {'id': 'EXD', 'name': 'Exeter St Davids', 'kind': 'STATION', 'size': 4, 'major': True},
        {'id': 'TIV', 'name': 'Tiverton Parkway', 'kind': 'STATION', 'size': 2, 'major': True},
        {'id': 'TAU', 'name': 'Taunton', 'kind': 'STATION', 'size': 3, 'major': True},
        {'id': 'BRI', 'name': 'Bristol Temple Meads', 'kind': 'STATION', 'size': 5, 'major': True},
        {'id': 'CDI', 'name': 'Crediton', 'kind': 'STATION', 'size': 2, 'major': False},
        {'id': 'YEO', 'name': 'Yeoford', 'kind': 'STATION', 'size': 2, 'major': False},
        {'id': 'EGG', 'name': 'Eggesford', 'kind': 'STATION', 'size': 2, 'major': False},
        {'id': 'BNP', 'name': 'Barnstaple', 'kind': 'STATION', 'size': 3, 'major': False},
        {'id': 'OKE', 'name': 'Okehampton', 'kind': 'STATION', 'size': 2, 'major': False},
        {'id': 'EXM', 'name': 'Exmouth', 'kind': 'STATION', 'size': 2, 'major': False},
        {'id': 'TOP', 'name': 'Topsham', 'kind': 'STATION', 'size': 1, 'major': False},
        {'id': 'DIG', 'name': 'Digby & Sowton', 'kind': 'STATION', 'size': 1, 'major': False},
        {'id': 'TQY', 'name': 'Torquay', 'kind': 'STATION', 'size': 2, 'major': False},
        {'id': 'PGN', 'name': 'Paignton', 'kind': 'STATION', 'size': 2, 'major': False},
        {'id': 'HON', 'name': 'Honiton', 'kind': 'STATION', 'size': 2, 'major': False},
        {'id': 'EXD_W', 'name': 'Exeter West Jn', 'kind': 'JUNCTION'},
        {'id': 'CWB', 'name': 'Cowley Bridge Jn', 'kind': 'JUNCTION'},
        {'id': 'YEO_JN', 'name': 'Yeoford Jn', 'kind': 'JUNCTION'},
        {'id': 'TAU_W', 'name': 'Taunton West Jn', 'kind': 'JUNCTION'},
        {'id': 'EXJ', 'name': 'Exmouth Jn', 'kind': 'JUNCTION'},
    ],
    'edges': [
        {
            'id': 'E_PLY_NWP',
            'a': 'PLY',
            'b': 'NWP',
            'km': 42,
            'speed_kmh': 125,
            'tracks': 2,
            'bidir': True,
        },
        {
            'id': 'E_NWP_EXDW',
            'a': 'NWP',
            'b': 'EXD_W',
            'km': 32,
            'speed_kmh': 125,
            'tracks': 2,
            'bidir': True,
        },
        {
            'id': 'E_EXDW_EXD',
            'a': 'EXD_W',
            'b': 'EXD',
            'km': 2.0,
            'speed_kmh': 60,
            'tracks': 2,
            'bidir': True,
        },
        {
            'id': 'E_EXDW_CWB',
            'a': 'EXD_W',
            'b': 'CWB',
            'km': 3.0,
            'speed_kmh': 70,
            'tracks': 1,
            'bidir': True,
        },
        {
            'id': 'E_CWB_EXD',
            'a': 'CWB',
            'b': 'EXD',
            'km': 1.5,
            'speed_kmh': 50,
            'tracks': 1,
            'bidir': True,
        },
        {
            'id': 'E_CWB_CDI',
            'a': 'CWB',
            'b': 'CDI',
            'km': 7.5,
            'speed_kmh': 80,
            'tracks': 1,
            'bidir': True,
        },
        {
            'id': 'E_CDI_YEOJN',
            'a': 'CDI',
            'b': 'YEO_JN',
            'km': 6.5,
            'speed_kmh': 85,
            'tracks': 1,
            'bidir': True,
        },
        {
            'id': 'E_YEOJN_YEO',
            'a': 'YEO_JN',
            'b': 'YEO',
            'km': 0.5,
            'speed_kmh': 40,
            'tracks': 1,
            'bidir': True,
        },
        {
            'id': 'E_YEOJN_EGG',
            'a': 'YEO_JN',
            'b': 'EGG',
            'km': 14.0,
            'speed_kmh': 85,
            'tracks': 1,
            'bidir': True,
        },
        {
            'id': 'E_EGG_BNP',
            'a': 'EGG',
            'b': 'BNP',
            'km': 25.0,
            'speed_kmh': 85,
            'tracks': 1,
            'bidir': True,
        },
        {
            'id': 'E_YEOJN_OKE',
            'a': 'YEO_JN',
            'b': 'OKE',
            'km': 25.0,
            'speed_kmh': 90,
            'tracks': 1,
            'bidir': True,
        },
        {
            'id': 'E_EXD_TIV',
            'a': 'EXD',
            'b': 'TIV',
            'km': 27,
            'speed_kmh': 125,
            'tracks': 2,
            'bidir': True,
        },
        {
            'id': 'E_TIV_TAUW',
            'a': 'TIV',
            'b': 'TAU_W',
            'km': 48,
            'speed_kmh': 125,
            'tracks': 2,
            'bidir': True,
        },
        {
            'id': 'E_TAUW_TAU',
            'a': 'TAU_W',
            'b': 'TAU',
            'km': 2.5,
            'speed_kmh': 60,
            'tracks': 2,
            'bidir': True,
        },
        {
            'id': 'E_TAUW_BRI',
            'a': 'TAU_W',
            'b': 'BRI',
            'km': 79,
            'speed_kmh': 125,
            'tracks': 2,
            'bidir': True,
        },
        {
            'id': 'E_EXD_EXJ',
            'a': 'EXD',
            'b': 'EXJ',
            'km': 3.0,
            'speed_kmh': 70,
            'tracks': 2,
            'bidir': True,
        },
        {
            'id': 'E_EXJ_DIG',
            'a': 'EXJ',
            'b': 'DIG',
            'km': 5.5,
            'speed_kmh': 90,
            'tracks': 2,
            'bidir': True,
        },
        {
            'id': 'E_DIG_TOP',
            'a': 'DIG',
            'b': 'TOP',
            'km': 7.0,
            'speed_kmh': 90,
            'tracks': 1,
            'bidir': True,
        },
        {
            'id': 'E_TOP_EXM',
            'a': 'TOP',
            'b': 'EXM',
            'km': 7.0,
            'speed_kmh': 90,
            'tracks': 1,
            'bidir': True,
        },
        {
            'id': 'E_NWP_TQY',
            'a': 'NWP',
            'b': 'TQY',
            'km': 23.0,
            'speed_kmh': 90,
            'tracks': 1,
            'bidir': True,
        },
        {
            'id': 'E_TQY_PGN',
            'a': 'TQY',
            'b': 'PGN',
            'km': 6.0,
            'speed_kmh': 80,
            'tracks': 1,
            'bidir': True,
        },
        {
            'id': 'E_EXD_HON',
            'a': 'EXD',
            'b': 'HON',
            'km': 25.0,
            'speed_kmh': 100,
            'tracks': 1,
            'bidir': True,
        },
    ],
}
PANEL_POS_DEFAULT: dict[str, tuple[int, int]] = {
    'PLY': (2, 8),
    'NWP': (22, 8),
    'EXD_W': (38, 8),
    'EXD': (52, 8),
    'TIV': (68, 8),
    'TAU_W': (86, 8),
    'TAU': (96, 8),
    'BRI': (112, 6),
    'CWB': (44, 10),
    'CDI': (44, 14),
    'YEO_JN': (44, 17),
    'YEO': (58, 17),
    'EGG': (44, 20),
    'BNP': (44, 23),
    'OKE': (30, 20),
    'EXJ': (60, 10),
    'DIG': (70, 12),
    'TOP': (78, 14),
    'EXM': (88, 16),
    'TQY': (22, 12),
    'PGN': (22, 15),
    'HON': (74, 5),
}

# -----------------------------
# Rolling stock + services
# -----------------------------

TRAIN_MODELS: dict[str, TrainModel] = {
    'dmu': TrainModel('dmu', 'Local DMU (2-car)', 'passenger', cost=450, cruise_kmh=85, capacity=150),
    'emu': TrainModel('emu', 'Regional EMU', 'passenger', cost=900, cruise_kmh=105, capacity=230),
    'hstk': TrainModel('hstk', 'Intercity Set', 'passenger', cost=2600, cruise_kmh=145, capacity=360),
    'fr8': TrainModel('fr8', 'Freight Loco', 'freight', cost=1200, cruise_kmh=90, capacity=900),
    'hhv': TrainModel('hhv', 'Heavy Hauler', 'freight', cost=4200, cruise_kmh=75, capacity=1800),
}

SERVICE_TEMPLATES: list[ServiceTemplate] = [
    ServiceTemplate(
        'sw_local',
        'SW Local: Plymouth–Newton Abbot–Exeter–Tiverton–Taunton',
        'passenger',
        'local',
        ['PLY', 'NWP', 'EXD', 'TIV', 'TAU'],
        fare_per_km=0.09,
        target_headway_s=3600,
        grace_pct=0.10,
    ),
    ServiceTemplate(
        'sw_fast',
        'SW Fast: Plymouth–Exeter–Taunton (Express)',
        'passenger',
        'express',
        ['PLY', 'EXD', 'TAU'],
        fare_per_km=0.10,
        target_headway_s=7200,
        grace_pct=0.10,
    ),
    ServiceTemplate(
        'tarka_local',
        'Tarka Local: Exeter–Crediton–Yeoford–Eggesford–Barnstaple',
        'passenger',
        'local',
        ['EXD', 'CDI', 'YEO', 'EGG', 'BNP'],
        fare_per_km=0.082,
        target_headway_s=3600,
        grace_pct=0.10,
    ),
    ServiceTemplate(
        'dart_local',
        'Dartmoor Local: Exeter–Crediton–Okehampton',
        'passenger',
        'local',
        ['EXD', 'CDI', 'OKE'],
        fare_per_km=0.084,
        target_headway_s=7200,
        grace_pct=0.10,
    ),
    ServiceTemplate(
        'sw_freight',
        'SW Freight: Plymouth–Exeter–Taunton',
        'freight',
        'freight',
        ['PLY', 'EXD', 'TAU'],
        rate_per_ton_km=0.055,
        target_headway_s=10800,
        grace_pct=0.10,
    ),
    ServiceTemplate(
        'exm_local',
        'Exmouth Local: Exeter–Topsham–Exmouth',
        'passenger',
        'local',
        ['EXD', 'TOP', 'EXM'],
        fare_per_km=0.080,
        target_headway_s=1800,
        grace_pct=0.10,
    ),
    ServiceTemplate(
        'torbay_local',
        'Torbay Local: Newton Abbot–Torquay–Paignton',
        'passenger',
        'local',
        ['NWP', 'TQY', 'PGN'],
        fare_per_km=0.082,
        target_headway_s=3600,
        grace_pct=0.10,
    ),
    ServiceTemplate(
        'hon_local',
        'East Devon Local: Exeter–Honiton',
        'passenger',
        'local',
        ['EXD', 'HON'],
        fare_per_km=0.086,
        target_headway_s=3600,
        grace_pct=0.10,
    ),
]

# -----------------------------
# Realism overrides loading
# -----------------------------


@dataclass
class RealismInfo:
    path: str = ''
    loaded: bool = False
    edge_overrides: dict[str, dict] = field(default_factory=dict)


def realism_path_for(region_id: str) -> str:
    return os.path.join(REALISM_DIR, f'{region_id}.json')


def load_realism_overrides(region_id: str) -> RealismInfo:
    os.makedirs(REALISM_DIR, exist_ok=True)
    path = realism_path_for(region_id)
    if not os.path.exists(path):
        # If missing and devon: seed from embedded defaults (created on first run)
        # Otherwise: create an empty scaffold.
        if region_id != 'devon':
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(
                    {
                        'meta': {'region_id': region_id, 'notes': ['Fill edges{} with overrides.']},
                        'edges': {},
                    },
                    f,
                    indent=2,
                )
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        edge_overrides = dict(data.get('edges', {}))
        return RealismInfo(path=path, loaded=True, edge_overrides=edge_overrides)
    except Exception:
        return RealismInfo(path=path, loaded=False, edge_overrides={})


def apply_realism_overrides_to_world(world: 'World', realism: RealismInfo) -> int:
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


# -----------------------------
# World
# -----------------------------


class World:
    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, Edge] = {}
        self.panel_pos: dict[str, tuple[int, int]] = dict(PANEL_POS_DEFAULT)
        self.realism: RealismInfo = RealismInfo()
        self.realism_applied: int = 0

    def load_region_file(self, region_id: str) -> dict:
        os.makedirs(REGION_DIR, exist_ok=True)
        path = os.path.join(REGION_DIR, f'{region_id}.json')
        if not os.path.exists(path) and region_id == 'devon':
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(DEVON_BUNDLE, f, indent=2)
        with open(path, encoding='utf-8') as f:
            bundle = json.load(f)

        # Merge devon built-in non-destructively
        if bundle.get('region_id') == 'devon':
            bn = {n.get('id') for n in bundle.get('nodes', [])}
            be = {e.get('id') for e in bundle.get('edges', [])}
            for n in DEVON_BUNDLE.get('nodes', []):
                if n.get('id') not in bn:
                    bundle.setdefault('nodes', []).append(n)
            for e in DEVON_BUNDLE.get('edges', []):
                if e.get('id') not in be:
                    bundle.setdefault('edges', []).append(e)

        # Nodes/edges
        for nd in bundle.get('nodes', []):
            self.nodes[nd['id']] = Node(
                id=nd['id'],
                name=nd.get('name', nd['id']),
                kind=nd.get('kind', 'STATION'),
                size=int(nd.get('size', 1)),
                major=bool(nd.get('major', False)),
            )
        for ed in bundle.get('edges', []):
            self.edges[ed['id']] = Edge(
                id=ed['id'],
                a=ed['a'],
                b=ed['b'],
                km=float(ed.get('km', 1.0)),
                speed_kmh=float(ed.get('speed_kmh', 120.0)),
                tracks=int(ed.get('tracks', 1)),
                bidir=bool(ed.get('bidir', True)),
            )

        # Load + apply realism overrides
        self.realism = load_realism_overrides(region_id)
        self.realism_applied = apply_realism_overrides_to_world(self, self.realism)
        return bundle


# -----------------------------
# Utility
# -----------------------------


def fmt_money(x: float) -> str:
    if x >= 1_000_000:
        return f'£{x / 1_000_000:.2f}M'
    if x >= 1_000:
        return f'£{x / 1_000:.2f}K'
    return f'£{x:.2f}'


def log_msg(state: GameState, msg: str) -> None:
    state.msg_log.append(msg)
    if len(state.msg_log) > 320:
        state.msg_log = state.msg_log[-320:]


def log_event(state: GameState, msg: str, level: str = 'event') -> None:
    if state.verbose or level in ('important', 'error'):
        log_msg(state, msg)


def set_pinned_override(state: GameState, title: str, lines: list[str], ttl_real_s: float = 8.0) -> None:
    state.pinned_override_lines = ([title] + list(lines))[:14]
    ttl_game = float(ttl_real_s) * float(max(1.0, state.time_scale))
    state.pinned_override_until_game = float(state.game_time) + ttl_game


def push_history(state: GameState, cmd: str) -> None:
    cmd = cmd.strip()
    if not cmd:
        return
    if state.cmd_history and state.cmd_history[-1] == cmd:
        state.cmd_hist_idx = -1
        return
    state.cmd_history.append(cmd)
    if len(state.cmd_history) > 200:
        state.cmd_history = state.cmd_history[-200:]
    state.cmd_hist_idx = -1


# -----------------------------
# Headway KPIs (Option B)
# -----------------------------

HEADWAY_WINDOW_TRIPS = 20


def record_service_completion(
    state: GameState, service_id: str, now_t: float, target_headway_s: int, grace_pct: float
) -> None:
    last = state.svc_last_complete.get(service_id)
    state.svc_last_complete[service_id] = float(now_t)
    if last is None:
        return

    actual = float(now_t) - float(last)
    hist = state.svc_headway_hist_s.get(service_id, [])
    hist.append(actual)
    if len(hist) > HEADWAY_WINDOW_TRIPS:
        hist = hist[-HEADWAY_WINDOW_TRIPS:]
    state.svc_headway_hist_s[service_id] = hist

    allowed = float(target_headway_s) * (1.0 + float(grace_pct))
    on_time = 1 if actual <= allowed else 0
    flags = state.svc_ontime_flags.get(service_id, [])
    flags.append(on_time)
    if len(flags) > HEADWAY_WINDOW_TRIPS:
        flags = flags[-HEADWAY_WINDOW_TRIPS:]
    state.svc_ontime_flags[service_id] = flags


def service_ontime_pct(state: GameState, service_id: str) -> float | None:
    flags = state.svc_ontime_flags.get(service_id)
    if not flags:
        return None
    return 100.0 * (sum(flags) / len(flags))


def service_bonus_multiplier(state: GameState, service_id: str) -> float:
    pct = service_ontime_pct(state, service_id)
    if pct is None:
        return 1.0
    if pct >= 95.0:
        return 1.10
    if pct >= 85.0:
        return 1.06
    if pct >= 70.0:
        return 1.03
    return 1.0


def service_headway_stats(state: GameState, service_id: str) -> tuple[float | None, float | None]:
    hist = state.svc_headway_hist_s.get(service_id)
    if not hist:
        return None, None
    return float(hist[-1]), float(sum(hist) / len(hist))


def service_headway_health_pct(state: GameState, service_id: str, target_headway_s: int) -> float | None:
    _last, avg = service_headway_stats(state, service_id)
    if avg is None or target_headway_s <= 0:
        return None
    dev = abs(avg - float(target_headway_s)) / float(target_headway_s)
    score = max(0.0, 100.0 * (1.0 - dev))
    return min(100.0, score)


def network_headway_health_pct(state: GameState, services: dict[str, Service]) -> float | None:
    total = 0.0
    wsum = 0.0
    for sid, svc in services.items():
        pct = service_headway_health_pct(state, sid, svc.target_headway_s)
        if pct is None:
            continue
        w = 1.0 if svc.kind == 'passenger' else 0.5
        total += pct * w
        wsum += w
    if wsum <= 0.0:
        return None
    return total / wsum


def network_ontime_pct(state: GameState, services: dict[str, Service]) -> float | None:
    total = 0.0
    total_w = 0.0
    for sid, svc in services.items():
        pct = service_ontime_pct(state, sid)
        if pct is None:
            continue
        w = 1.0 if svc.kind == 'passenger' else 0.5
        total += pct * w
        total_w += w
    if total_w <= 0.0:
        return None
    return total / total_w


# -----------------------------
# Ops dashboard
# -----------------------------


def build_ops_rows(state: GameState, services: dict[str, Service]) -> list[dict]:
    rows = []
    for sid, s in services.items():
        last_h, avg_h = service_headway_stats(state, sid)
        rows.append(
            {
                'sid': sid,
                'kind': s.kind,
                'pattern': s.pattern,
                'tgt_m': int(s.target_headway_s // 60),
                'last_h': last_h,
                'avg_h': avg_h,
                'pct': service_ontime_pct(state, sid),
                'hh': service_headway_health_pct(state, sid, s.target_headway_s),
                'bonus': service_bonus_multiplier(state, sid),
                'last': state.svc_last_complete.get(sid),
            }
        )
    return rows


def ops_tier_role(pct: float | None) -> str:
    if pct is None:
        return 'DIM'
    if pct >= 95.0:
        return 'GOOD'
    if pct >= 85.0:
        return 'OK'
    if pct >= 70.0:
        return 'WARN'
    return 'BAD'


def ops_dashboard_lines(state: GameState, services: dict[str, Service], now_t: float) -> list[str]:
    net_ot = network_ontime_pct(state, services)
    net_hw = network_headway_health_pct(state, services)
    ot_s = f'{net_ot:5.1f}%' if net_ot is not None else ' n/a '
    hw_s = f'{net_hw:5.1f}%' if net_hw is not None else ' n/a '

    lines: list[str] = []
    lines.append(f'OPS DASHBOARD  On-time: {ot_s}  Headway: {hw_s}')

    rows = [r for r in build_ops_rows(state, services) if r['pct'] is not None or r['hh'] is not None]
    rows.sort(key=lambda r: (-(r['pct'] or 0.0), -(r['hh'] or 0.0)))

    best = rows[:3]
    worst = list(reversed(rows[-3:])) if len(rows) >= 3 else []

    def fmt_row(r):
        ago = '-'
        if r['last'] is not None:
            ago_s = max(0, int(float(now_t) - float(r['last'])))
            ago = f'{ago_s // 60}m'
        last_m = f'{int(r["last_h"] // 60)}m' if r['last_h'] is not None else 'n/a'
        avg_m = f'{int(r["avg_h"] // 60)}m' if r['avg_h'] is not None else 'n/a'
        hh_s2 = f'{r["hh"]:4.0f}%' if r['hh'] is not None else ' n/a'
        pct_s2 = f'{r["pct"]:5.1f}%' if r['pct'] is not None else '  n/a'
        return f'{r["sid"]:<12} {pct_s2}  hw {last_m:>4}/{avg_m:<4} {hh_s2:>4}  x{r["bonus"]:.2f}  last {ago}'

    if best:
        lines.append('Best:')
        for r in best:
            lines.append('  ' + fmt_row(r))
    else:
        lines.append('Best: (need more trips)')

    if worst and len(rows) > 3:
        lines.append('Worst:')
        for r in worst:
            lines.append('  ' + fmt_row(r))

    lines.append("Tip: press 'o' or run 'ops detail' for full ops report")
    return lines[:14]


def build_ops_report(state: GameState, services: dict[str, Service], now_t: float) -> str:
    rows = build_ops_rows(state, services)
    rows.sort(
        key=lambda r: (
            -1 if (r['pct'] is None and r['hh'] is None) else 0,
            -(r['pct'] or 0.0),
            -(r['hh'] or 0.0),
            r['sid'],
        )
    )
    net_ot = network_ontime_pct(state, services)
    net_hw = network_headway_health_pct(state, services)

    out: list[str] = []
    out.append('OPERATIONS DASHBOARD (full)')
    out.append(f'Network on-time: {net_ot:5.1f}%' if net_ot is not None else 'Network on-time: n/a')
    out.append(f'Network headway: {net_hw:5.1f}%' if net_hw is not None else 'Network headway: n/a')
    out.append('')
    out.append('Service        Kind       Pattern   Target  Headway(last/avg)  On-time  HW%   Bonus')
    out.append('----------------------------------------------------------------------------')
    for r in rows:
        tgt = f'{r["tgt_m"]:>4}m'
        last_m = f'{int(r["last_h"] // 60)}m' if r['last_h'] is not None else ' n/a'
        avg_m = f'{int(r["avg_h"] // 60)}m' if r['avg_h'] is not None else ' n/a'
        pct_s = f'{r["pct"]:5.1f}%' if r['pct'] is not None else '  n/a'
        hh_s = f'{r["hh"]:5.1f}%' if r['hh'] is not None else '  n/a'
        out.append(
            f'{r["sid"]:<12} {r["kind"]:<10} {r["pattern"]:<8} {tgt:>6}   {last_m:>4}/{avg_m:<4}       {pct_s:>6}  {hh_s:>6}  x{r["bonus"]:.2f}'
        )
    out.append('')
    out.append(
        'Notes: headway measured between terminus completions; HW% is closeness of avg headway to target (0..100).'
    )
    return '\n'.join(out)


# -----------------------------
# Graph/pathfinding (directionality)
# -----------------------------


def build_active_adjacency(world: World, state: GameState) -> dict[str, list[tuple[str, str, float]]]:
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
    if start == goal:
        return [start], [], 0.0
    dist = {start: 0.0}
    prev: dict[str, tuple[str, str]] = {}
    pq = [(0.0, start)]
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


# -----------------------------
# Discovery/unlocks
# -----------------------------


def initial_discovery(world: World, state: GameState, home: str, hop_limit: int = 3) -> None:
    discovered_nodes: set[str] = {home}
    discovered_edges: set[str] = set()
    full_adj: dict[str, list[tuple[str, str]]] = {}
    for eid, e in world.edges.items():
        full_adj.setdefault(e.a, []).append((e.b, eid))
        if e.bidir:
            full_adj.setdefault(e.b, []).append((e.a, eid))
    q = [(home, 0)]
    seen = {home}
    while q:
        u, depth = q.pop(0)
        if depth >= hop_limit:
            continue
        for v, eid in full_adj.get(u, []):
            discovered_edges.add(eid)
            discovered_nodes.add(v)
            if v not in seen:
                seen.add(v)
                q.append((v, depth + 1))
    state.discovered_nodes = sorted(discovered_nodes)
    state.discovered_edges = sorted(discovered_edges)


def unlock_cost(world: World, eid: str) -> int:
    e = world.edges[eid]
    cost = 200 + int(120 * e.km)
    if e.tracks >= 2:
        cost += int(200 * e.km)
    return cost


def frontier_unlocks(world: World, state: GameState, max_items: int = 12) -> list[tuple[str, str, int]]:
    disc_nodes = set(state.discovered_nodes)
    disc_edges = set(state.discovered_edges)
    opts: list[tuple[str, str, int]] = []
    for eid, e in world.edges.items():
        if eid in disc_edges:
            continue
        if (e.a in disc_nodes) ^ (e.b in disc_nodes):
            arrow = '↔' if e.bidir else '→'
            opts.append(
                (
                    eid,
                    f'{e.a} {arrow} {e.b}  ({e.km:.1f}km, tracks={e.tracks})',
                    unlock_cost(world, eid),
                )
            )
    opts.sort(key=lambda x: x[2])
    return opts[:max_items]


# -----------------------------
# Services availability
# -----------------------------


def build_available_services(world: World, state: GameState) -> dict[str, Service]:
    disc_nodes = set(state.discovered_nodes)
    adj = build_active_adjacency(world, state)
    services: dict[str, Service] = {}
    for tmpl in SERVICE_TEMPLATES:
        if not all(c in disc_nodes for c in tmpl.calls):
            continue
        ok = True
        for i in range(len(tmpl.calls) - 1):
            _, _, dist = dijkstra_path(adj, tmpl.calls[i], tmpl.calls[i + 1])
            if math.isinf(dist):
                ok = False
                break
        if not ok:
            continue
        services[tmpl.id] = Service(
            id=tmpl.id,
            name=tmpl.name,
            kind=tmpl.kind,
            pattern=tmpl.pattern,
            calls=list(tmpl.calls),
            fare_per_km=tmpl.fare_per_km,
            rate_per_ton_km=tmpl.rate_per_ton_km,
            target_headway_s=tmpl.target_headway_s,
            grace_pct=tmpl.grace_pct,
        )
    return services


# -----------------------------
# Blocks
# -----------------------------


def make_block_for_edge(e: Edge) -> dict:
    return {'mode': 'single', 'occ': None} if e.tracks <= 1 else {'mode': 'dir', 'occ_fwd': None, 'occ_rev': None}


def rebuild_blocks(world: World, state: GameState, blocks: dict[str, dict]) -> None:
    """Rebuild blocks for discovered edges, respecting current tracks in world.edges."""
    blocks.clear()
    for eid in state.discovered_edges:
        e = world.edges.get(eid)
        if e:
            blocks[eid] = make_block_for_edge(e)


def block_is_free(block: dict, dir_sign: int) -> bool:
    if block['mode'] == 'single':
        return block['occ'] is None
    return (block['occ_fwd'] is None) if dir_sign > 0 else (block['occ_rev'] is None)


def block_reserve(block: dict, tid: int, dir_sign: int) -> None:
    if block['mode'] == 'single':
        block['occ'] = tid
    else:
        if dir_sign > 0:
            block['occ_fwd'] = tid
        else:
            block['occ_rev'] = tid


def block_release(block: dict, tid: int) -> None:
    if block['mode'] == 'single':
        if block.get('occ') == tid:
            block['occ'] = None
    else:
        if block.get('occ_fwd') == tid:
            block['occ_fwd'] = None
        if block.get('occ_rev') == tid:
            block['occ_rev'] = None


# -----------------------------
# Movement + revenue
# -----------------------------


def edge_travel_time_s(edge: Edge, model: TrainModel, service: Service) -> float:
    eff = min(model.cruise_kmh, edge.speed_kmh)
    if service.kind == 'freight':
        eff *= 0.85
    if service.pattern == 'local':
        eff *= 0.92
    eff = max(10.0, eff)
    return max(20.0, (edge.km / eff) * 3600.0)


def dwell_time_s(world: World, service: Service, nid: str) -> int:
    n = world.nodes.get(nid)
    return service.dwell_major_s if (n and n.major) else service.dwell_minor_s


def passenger_revenue(world: World, service: Service, model: TrainModel, km: float, a: str, b: str) -> float:
    sa = world.nodes[a].size if a in world.nodes else 2
    sb = world.nodes[b].size if b in world.nodes else 2
    base = 18.0 * (sa + sb)
    coverage, premium = (
        (service.local_coverage, 1.0)
        if service.pattern == 'local'
        else (service.express_coverage, service.express_premium)
    )
    riders = min(model.capacity, base * coverage)
    return riders * km * (service.fare_per_km * premium)


def freight_revenue(service: Service, model: TrainModel, km: float) -> float:
    return model.capacity * 0.75 * km * service.rate_per_ton_km


# -----------------------------
# Map helpers (canonical dog-legs)
# -----------------------------


def viewport_transform(state: GameState, wx: float, wy: float, win_w: int, win_h: int) -> tuple[int, int]:
    ox, oy = 1, 1
    iw = max(1, win_w - 2)
    ih = max(1, win_h - 2)
    sx = int((wx - state.view_cx) * state.view_zoom + iw / 2) + ox
    sy = int((wy - state.view_cy) * state.view_zoom + ih / 2) + oy
    return sx, sy


def in_bounds(x: int, y: int, win_w: int, win_h: int) -> bool:
    return 1 <= x < win_w - 1 and 1 <= y < win_h - 1


def draw_line_segment(win, x1: int, y1: int, x2: int, y2: int, ch: str, attr: int = 0) -> None:
    if y1 == y2:
        for x in range(min(x1, x2), max(x1, x2) + 1):
            safe_addch(win, y1, x, ch, attr)
    elif x1 == x2:
        for y in range(min(y1, y2), max(y1, y2) + 1):
            safe_addch(win, y, x1, ch if ch != '=' else '|', attr)


def dogleg_points_for_edge(world: World, edge: Edge) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]] | None:
    if edge.a not in world.panel_pos or edge.b not in world.panel_pos:
        return None
    x0, y0 = world.panel_pos[edge.a]
    x1, y1 = world.panel_pos[edge.b]
    if x0 == x1 or y0 == y1:
        return ((x0, y0), (x1, y1), (x1, y1))
    elbow = (x0, y1)
    return ((x0, y0), elbow, (x1, y1))


def train_marker(t: Train) -> str:
    return '▶' if t.state == 'RUN' else ('⛔' if t.state == 'WAIT' else ('■' if t.state == 'DWELL' else '·'))


def train_role(t: Train) -> str:
    if t.state == 'RUN':
        return 'RUN'
    if t.state == 'WAIT':
        return 'WAIT'
    if t.state == 'DWELL':
        return 'DWELL'
    return 'IDLE'


def estimate_train_world_pos(world: World, t: Train, now_t: float) -> tuple[float, float] | None:
    if t.state == 'RUN' and t.current_edge and t.at_node and t.current_edge in world.edges:
        e = world.edges[t.current_edge]
        dep = t.at_node
        pts = dogleg_points_for_edge(world, e)
        if not pts:
            return None
        (x0, y0), (xe, ye), (x1, y1) = pts
        denom = max(1e-6, float(t.edge_arrive_t) - float(t.edge_depart_t))
        p = (float(now_t) - float(t.edge_depart_t)) / denom
        p = max(0.0, min(1.0, p))

        poly = [(x0, y0), (xe, ye), (x1, y1)]
        if dep == e.b:
            poly = list(reversed(poly))

        (sx0, sy0), (sx1, sy1), (sx2, sy2) = poly
        seg1 = abs(sx1 - sx0) + abs(sy1 - sy0)
        seg2 = abs(sx2 - sx1) + abs(sy2 - sy1)
        total = max(1e-6, seg1 + seg2)
        d = p * total

        if d <= seg1:
            if sx0 == sx1:
                sgn = 1 if sy1 > sy0 else -1
                return (float(sx0), float(sy0 + sgn * d))
            sgn = 1 if sx1 > sx0 else -1
            return (float(sx0 + sgn * d), float(sy0))

        d2 = d - seg1
        if sx1 == sx2:
            sgn = 1 if sy2 > sy1 else -1
            return (float(sx1), float(sy1 + sgn * d2))
        sgn = 1 if sx2 > sx1 else -1
        return (float(sx1 + sgn * d2), float(sy1))

    if t.at_node and t.at_node in world.panel_pos:
        x, y = world.panel_pos[t.at_node]
        return (float(x), float(y))
    return None


def label_for_node(nid: str, kind: str) -> str:
    if kind != 'JUNCTION':
        return nid[:3]
    overrides = {'EXD_W': 'XDW', 'TAU_W': 'TUW', 'YEO_JN': 'YJN'}
    if nid in overrides:
        return overrides[nid]
    if '_' in nid:
        base, suf = nid.split('_', 1)
        base = base.upper()
        suf = suf.upper()
        if len(suf) >= 2:
            return (base[:1] + suf[:2]).upper()
        if len(base) >= 2:
            return (base[0] + base[1] + suf[:1]).upper()
    return nid[:3]


# -----------------------------
# Path sync helpers
# -----------------------------


def path_is_aligned(train) -> bool:
    """True if cached path starts at the train's current node."""
    return train.at_node is not None and bool(getattr(train, 'path_nodes', [])) and train.path_nodes[0] == train.at_node


def consume_path_step(train, departed: str, arrived: str) -> None:
    """Advance cached path if the train just traversed the first planned step."""
    if (
        getattr(train, 'path_nodes', None)
        and train.path_nodes[0] == departed
        and len(train.path_nodes) >= 2
        and train.path_nodes[1] == arrived
    ):
        train.path_nodes.pop(0)
        if getattr(train, 'path_edges', None):
            train.path_edges.pop(0)


# -----------------------------
# Track realism: direction check
# -----------------------------


def edge_allows(world: World, eid: str, dep: str) -> bool:
    e = world.edges.get(eid)
    if not e:
        return False
    if dep == e.a:
        return True
    if dep == e.b and e.bidir:
        return True
    return False


# -----------------------------
# Train simulation
# -----------------------------


def plan_to_next_call(world: World, state: GameState, train: Train, service: Service, adj) -> bool:
    if train.at_node is None:
        return False
    target = service.calls[train.call_index]
    nodes, edges, dist = dijkstra_path(adj, train.at_node, target)
    if math.isinf(dist):
        train.path_nodes = [train.at_node]
        train.path_edges = []
        return False
    train.path_nodes = nodes
    train.path_edges = edges
    return True


def advance_call_index(train: Train, service: Service) -> None:
    nxt = train.call_index + train.direction
    if nxt < 0 or nxt >= len(service.calls):
        train.direction *= -1
        train.call_index += train.direction
    else:
        train.call_index = nxt


def step_train(
    world: World,
    state: GameState,
    train: Train,
    services: dict[str, Service],
    blocks: dict[str, dict],
    now_t: float,
) -> None:
    if train.service_id is None or train.service_id not in services:
        train.state = 'IDLE'
        train.next_event_t = 0.0
        train.current_edge = None
        train.path_nodes = []
        train.path_edges = []
        return

    service = services[train.service_id]
    model = TRAIN_MODELS[train.model_id]
    adj = build_active_adjacency(world, state)

    if train.at_node is None:
        train.at_node = state.home
    if train.at_node is None:
        train.state = 'IDLE'
        train.next_event_t = 0.0
        return

    if train.state == 'IDLE':
        train.call_index = 0
        train.direction = 1
        if train.at_node == service.calls[0]:
            train.state = 'DWELL'
            train.next_event_t = now_t + dwell_time_s(world, service, train.at_node)
        else:
            train.path_nodes = []
            train.path_edges = []
            plan_to_next_call(world, state, train, service, adj)
            train.state = 'WAIT'
            train.next_event_t = now_t
        return

    if train.state == 'DWELL':
        if now_t < train.next_event_t:
            return
        advance_call_index(train, service)
        train.state = 'WAIT'
        train.next_event_t = now_t
        return

    if train.state == 'WAIT':
        target = service.calls[train.call_index]
        if not path_is_aligned(train):
            train.path_nodes = []
            train.path_edges = []

        if train.at_node == target:
            train.state = 'DWELL'
            train.next_event_t = now_t + dwell_time_s(world, service, train.at_node)
            return

        if not train.path_edges:
            if not plan_to_next_call(world, state, train, service, adj):
                train.next_event_t = now_t + 1.0
                train.last_task = 'No path'
                return

        next_eid = train.path_edges[0]

        if not edge_allows(world, next_eid, train.at_node):
            train.path_nodes = []
            train.path_edges = []
            train.next_event_t = now_t + 1.0
            train.last_task = 'Replan (one-way)'
            return

        edge = world.edges[next_eid]
        dep = train.at_node
        arr = edge.b if dep == edge.a else edge.a
        dir_sign = +1 if (dep == edge.a and arr == edge.b) else -1

        if (not edge.bidir) and dir_sign < 0:
            train.path_nodes = []
            train.path_edges = []
            train.next_event_t = now_t + 1.0
            train.last_task = 'Replan (wrong way)'
            return

        if next_eid not in blocks:
            train.next_event_t = now_t + 1.0
            train.last_task = 'Edge locked'
            return

        blk = blocks[next_eid]
        if not block_is_free(blk, dir_sign):
            train.next_event_t = now_t + 1.0
            train.last_task = f'Wait signal ({next_eid})'
            return

        block_reserve(blk, train.id, dir_sign)
        travel_s = edge_travel_time_s(edge, model, service)
        train.state = 'RUN'
        train.current_edge = next_eid
        train.edge_depart_t = now_t
        train.edge_arrive_t = now_t + travel_s
        train.next_event_t = train.edge_arrive_t
        return

    if train.state == 'RUN':
        if (not train.next_event_t) and train.edge_arrive_t:
            train.next_event_t = train.edge_arrive_t
        if not train.next_event_t:
            train.next_event_t = now_t + 1.0
        if now_t < train.next_event_t:
            return

        eid = train.current_edge
        if not eid:
            train.state = 'WAIT'
            train.next_event_t = now_t
            return

        edge = world.edges[eid]
        departed = train.at_node
        arrived = edge.b if departed == edge.a else edge.a

        if arrived in (service.calls[0], service.calls[-1]):
            record_service_completion(state, service.id, now_t, service.target_headway_s, service.grace_pct)

        block_release(blocks[eid], train.id)
        if departed is not None:
            consume_path_step(train, departed, arrived)

        train.at_node = arrived
        train.current_edge = None

        if world.nodes.get(arrived) and world.nodes[arrived].kind == 'STATION':
            if service.kind == 'passenger':
                base_rev = passenger_revenue(world, service, model, edge.km, departed, arrived)
                rev = base_rev * service_bonus_multiplier(state, service.id)
            else:
                rev = freight_revenue(service, model, edge.km)
            state.money += rev
            train.last_revenue = rev

        target2 = service.calls[train.call_index]
        if arrived == target2:
            train.state = 'DWELL'
            train.next_event_t = now_t + dwell_time_s(world, service, arrived)
        else:
            train.state = 'WAIT'
            train.next_event_t = now_t
        return


def simulate(
    world: World,
    state: GameState,
    services: dict[str, Service],
    blocks: dict[str, dict],
    now_t: float,
) -> None:
    pq = []
    for idx, t in enumerate(state.trains):
        if not t.service_id:
            continue
        if t.state == 'RUN' and t.current_edge:
            if (not t.next_event_t) and t.edge_arrive_t:
                t.next_event_t = t.edge_arrive_t
            if not t.next_event_t:
                t.next_event_t = now_t + 1.0
        if t.next_event_t == 0.0:
            t.next_event_t = state.game_time
        heapq.heappush(pq, (float(t.next_event_t), idx))

    safety = 0
    while pq and pq[0][0] <= float(now_t):
        safety += 1
        if safety > 14000:
            log_event(state, 'Simulation safety stop (too many events).', level='error')
            break
        t_time, idx = heapq.heappop(pq)
        step_train(world, state, state.trains[idx], services, blocks, float(t_time))
        t = state.trains[idx]
        if t.service_id and t.service_id in services:
            heapq.heappush(pq, (float(t.next_event_t), idx))


# -----------------------------
# Save/load
# -----------------------------


def save_game(state: GameState) -> None:
    with open(SAVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(asdict(state), f, indent=2)


def load_game() -> GameState | None:
    if not os.path.exists(SAVE_FILE):
        return None
    with open(SAVE_FILE, encoding='utf-8') as f:
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


def new_game() -> GameState:
    st = GameState()
    st.trains.append(Train(id=0, model_id='dmu'))
    st.next_train_id = 1
    log_event(st, 'New game started. Quiet logging is ON (use verbose to toggle).', level='important')
    return st


# -----------------------------
# Commands
# -----------------------------

HELP_LINES = [
    'Commands:',
    '  help                          Show this help (F1)',
    '  status                        Summary',
    '  home <NODE>                   Set home station (e.g. home EXD)',
    '  models                        List train models',
    '  buy train <MODEL>             Buy a train',
    '  services                      List services incl headways',
    '  edges                         List discovered edges (tracks + direction)',
    '  realism                        Show realism override status',
    '  realism reload                 Reload realism overrides from disk',
    '  ops                           Short ops summary',
    '  ops detail                    Popup: full ops dashboard report',
    '  assign <TID> <SID>            Assign train to service',
    '  unlock                        List frontier unlocks',
    '  unlock <U#>                   Buy an unlock option',
    '  verbose [on|off]              Toggle verbose event logging',
    '  color on|off                  Enable/disable colour',
    '  theme <flavour>               Set Catppuccin flavour (latte/frappe/macchiato/mocha)',
    '  speed <N>                     Set speed multiplier',
    '  pause | resume                Pause/resume time',
    '  map                           Toggle map',
    '  save                          Save game',
    'Keys (when not typing): ARROWS pan | [ ] zoom | f follow0 | F unfollow | + - speed | p pause | o ops popup',
    'History: Ctrl+P/Ctrl+N always; ↑/↓ history only while typing',
]


def handle_command(
    world: World,
    state: GameState,
    services: dict[str, Service],
    blocks: dict[str, dict],
    cmdline: str,
    now_t: float,
) -> str:
    cmdline = cmdline.strip()
    if not cmdline:
        return ''
    parts = shlex.split(cmdline)
    c = parts[0].lower()

    if c in ('help', '?'):
        return '\n'.join(HELP_LINES)

    if c == 'save':
        save_game(state)
        return 'Saved.'

    if c == 'status':
        net_ot = network_ontime_pct(state, services)
        net_hw = network_headway_health_pct(state, services)
        ot = f'{net_ot:0.1f}%' if net_ot is not None else 'n/a'
        hw = f'{net_hw:0.1f}%' if net_hw is not None else 'n/a'
        return f'Money: {fmt_money(state.money)} | Home: {state.home or "(unset)"} | Trains: {len(state.trains)} | Speed: {state.time_scale:.0f}x {"(PAUSED)" if state.paused else ""} | OT {ot} | HW {hw}'

    if c == 'realism':
        if len(parts) >= 2 and parts[1].lower() == 'reload':
            world.realism = load_realism_overrides(DEFAULT_REGION_ID)
            world.realism_applied = apply_realism_overrides_to_world(world, world.realism)
            rebuild_blocks(world, state, blocks)
            return f'Realism reloaded: {world.realism_applied} overrides applied from {world.realism.path}'
        status = 'LOADED' if world.realism.loaded else 'NOT LOADED'
        return f'Realism overrides: {status} | file={world.realism.path} | overrides_applied={world.realism_applied}'

    if c == 'color' and len(parts) >= 2:
        v = parts[1].lower()
        if v in ('on', '1', 'true', 'yes'):
            state.color_enabled = True
            init_theme_colors(state)
            return 'Colour: ON'
        if v in ('off', '0', 'false', 'no'):
            state.color_enabled = False
            return 'Colour: OFF'
        return 'Usage: color on|off'

    if c == 'theme' and len(parts) >= 2:
        flav = parts[1].lower()
        if flav not in CATPPUCCIN:
            return 'Theme must be one of: latte, frappe, macchiato, mocha'
        state.theme_flavor = flav
        init_theme_colors(state)
        return f'Theme set to {flav}.'

    if c == 'home' and len(parts) >= 2:
        nid = parts[1].upper()
        n = world.nodes.get(nid)
        if not n:
            return f'Unknown node {nid}.'
        if n.kind != 'STATION':
            return 'Home must be a STATION node.'
        state.home = nid
        for tr in state.trains:
            if tr.at_node is None:
                tr.at_node = nid
        initial_discovery(world, state, nid, hop_limit=3)
        rebuild_blocks(world, state, blocks)
        if nid in world.panel_pos:
            state.view_cx, state.view_cy = world.panel_pos[nid]
        set_pinned_override(
            state,
            'HOME SET',
            [f'{nid} - {n.name}', 'Try: services / assign 0 tarka_local', 'Then: unlock'],
        )
        return f'Home station set to {nid}.'

    if c == 'models':
        lines = ['Train models:']
        for mid, m in TRAIN_MODELS.items():
            lines.append(
                f'  {mid:<5} {m.name:<18} kind={m.kind:<9} cost={fmt_money(m.cost):>8} speed={m.cruise_kmh:>4.0f} cap={m.capacity}'
            )
        return '\n'.join(lines)

    if c == 'buy' and len(parts) >= 3 and parts[1].lower() == 'train':
        mid = parts[2].lower()
        if mid not in TRAIN_MODELS:
            return 'Unknown model id.'
        m = TRAIN_MODELS[mid]
        if state.money < m.cost:
            return f'Not enough money. Need {fmt_money(m.cost)}.'
        state.money -= m.cost
        tid = state.next_train_id
        state.next_train_id += 1
        state.trains.append(Train(id=tid, model_id=mid, at_node=state.home))
        return f'Bought train {tid}.'

    if c == 'services':
        if not services:
            return 'No services available yet. Set home and unlock more track.'
        lines = ['Services: (target / headway last/avg / on-time / headway health / bonus)']
        for sid, s in services.items():
            tgt_m = int(s.target_headway_s // 60)
            last_h, avg_h = service_headway_stats(state, sid)
            last_m = f'{int(last_h // 60)}m' if last_h is not None else 'n/a'
            avg_m = f'{int(avg_h // 60)}m' if avg_h is not None else 'n/a'
            pct = service_ontime_pct(state, sid)
            pct_s = f'{pct:5.1f}%' if pct is not None else '  n/a '
            hh = service_headway_health_pct(state, sid, s.target_headway_s)
            hh_s = f'{hh:5.1f}%' if hh is not None else '  n/a '
            bonus = service_bonus_multiplier(state, sid)
            lines.append(
                f'  {sid:<12} tgt {tgt_m:>4}m  hw {last_m:>4}/{avg_m:<4}  OT {pct_s}  HW {hh_s}  x{bonus:.2f} | {s.pattern:<7} {s.kind:<9} {" → ".join(s.calls)}'
            )
        return '\n'.join(lines)

    if c == 'edges':
        if not state.discovered_edges:
            return 'No edges discovered yet.'
        lines = ['Discovered edges: (direction / tracks / km / speed)']
        for eid in state.discovered_edges:
            e = world.edges.get(eid)
            if not e:
                continue
            arrow = '↔' if e.bidir else '→'
            lines.append(
                f'  {eid:<12} {e.a} {arrow} {e.b:<6} tracks={e.tracks}  km={e.km:.1f}  vmax={e.speed_kmh:.0f}km/h'
            )
        return '\n'.join(lines)

    if c == 'ops':
        if len(parts) >= 2 and parts[1].lower() in ('detail', 'full'):
            return build_ops_report(state, services, now_t)
        net_ot = network_ontime_pct(state, services)
        net_hw = network_headway_health_pct(state, services)
        ot = f'{net_ot:0.1f}%' if net_ot is not None else 'n/a'
        hw = f'{net_hw:0.1f}%' if net_hw is not None else 'n/a'
        return f'Ops: network OT {ot}, network HW {hw}. Try: ops detail'

    if c == 'assign' and len(parts) >= 3:
        try:
            tid = int(parts[1])
        except ValueError:
            return 'Usage: assign <train_id> <service_id>'
        sid = parts[2]
        t = next((x for x in state.trains if x.id == tid), None)
        if not t:
            return 'Unknown train id.'
        if sid not in services:
            return 'Unknown/unavailable service id.'
        svc = services[sid]
        model = TRAIN_MODELS[t.model_id]
        if svc.kind == 'passenger' and model.kind == 'freight':
            return "That freight model can't run a passenger service."
        if svc.kind == 'freight' and model.kind == 'passenger':
            return "That passenger model can't run a freight service."
        t.service_id = sid
        t.state = 'IDLE'
        t.next_event_t = 0.0
        t.path_nodes = []
        t.path_edges = []
        t.current_edge = None
        return f'Assigned train {tid} to {sid}.'

    if c == 'unlock':
        if len(parts) == 1:
            opts = frontier_unlocks(world, state)
            if not opts:
                state.last_unlock_options = {}
                set_pinned_override(state, 'UNLOCK OPTIONS', ['(none available)'])
                return 'No frontier unlocks available.'
            state.last_unlock_options = {}
            lines = ["Frontier unlocks (buy with 'unlock U#'):"]
            for i, (eid, desc, cost) in enumerate(opts, start=1):
                oid = f'U{i}'
                state.last_unlock_options[oid] = eid
                lines.append(f'  {oid:<3} {desc:<38} cost {fmt_money(cost)}')
            set_pinned_override(state, 'UNLOCK OPTIONS', lines)
            return '\n'.join(lines)
        oid = parts[1].upper()
        if oid not in state.last_unlock_options:
            return "Unknown unlock option. Run 'unlock' to list options."
        eid = state.last_unlock_options[oid]
        if eid in state.discovered_edges:
            return 'Already unlocked.'
        cost = unlock_cost(world, eid)
        if state.money < cost:
            return f'Not enough money. Need {fmt_money(cost)}.'
        state.money -= cost
        e = world.edges[eid]
        state.discovered_edges = sorted(set(state.discovered_edges + [eid]))
        state.discovered_nodes = sorted(set(state.discovered_nodes + [e.a, e.b]))
        blocks[eid] = make_block_for_edge(e)
        set_pinned_override(
            state,
            'LAST UNLOCK',
            [f'{oid}: {e.a} {"↔" if e.bidir else "→"} {e.b}', f'Cost: {fmt_money(cost)}'],
        )
        return f'Unlocked {oid}: {e.a}{"↔" if e.bidir else "→"}{e.b}.'

    if c == 'verbose':
        if len(parts) == 1:
            state.verbose = not state.verbose
        else:
            v = parts[1].lower()
            if v in ('on', '1', 'true', 'yes'):
                state.verbose = True
            elif v in ('off', '0', 'false', 'no'):
                state.verbose = False
            else:
                return 'Usage: verbose [on|off]'
        return f'Verbose logging {"ON" if state.verbose else "OFF"}.'

    if c == 'speed' and len(parts) >= 2:
        try:
            n = float(parts[1])
        except ValueError:
            return 'Usage: speed <number>'
        if n < 0:
            return 'Speed must be >= 0.'
        state.time_scale = n
        state.paused = n == 0
        return f'Speed set to {state.time_scale:.0f}x.'

    if c == 'pause':
        state.paused = True
        return 'Paused.'

    if c == 'resume':
        state.paused = False
        if state.time_scale == 0:
            state.time_scale = 60.0
        return f'Resumed at {state.time_scale:.0f}x.'

    if c == 'map':
        state.ui_show_map = not state.ui_show_map
        return f'Map view {"ON" if state.ui_show_map else "OFF"}.'

    return "Unknown command. Try 'help'."


# -----------------------------
# Drawing panels
# -----------------------------


def draw_header(win, state: GameState, net_ot: float | None, net_hw: float | None):
    win.erase()
    win.box()
    apply_win_bkgd(win)
    maxy, maxx = win.getmaxyx()

    safe_addstr(win, 0, 2, ' Train Idle: UK Ops (v0.5.6.6.1) ', attr_for(state, 'TITLE', bold=True))
    safe_addstr(win, 1, 2, f'Money: {fmt_money(state.money)}', attr_for(state, 'HEADER'))
    safe_addstr(win, 1, 24, f'Home: {state.home or "(unset)"}', attr_for(state, 'HEADER'))

    sp = f'Speed: {state.time_scale:.0f}x {"PAUSED" if state.paused else ""}'
    safe_addstr(win, 1, 44, sp, attr_for(state, 'WARN' if state.paused else 'HEADER'))
    safe_addstr(
        win,
        1,
        max(2, maxx - 18),
        'Log: VERBOSE' if state.verbose else 'Log: quiet',
        attr_for(state, 'DIM'),
    )

    ot_s = f'{net_ot:0.1f}%' if net_ot is not None else 'n/a'
    hw_s = f'{net_hw:0.1f}%' if net_hw is not None else 'n/a'
    kpi_str = f'OT {ot_s} | HW {hw_s}'

    help_str = 'F1 help | q quit | +/- speed | p pause | [ ] zoom | ARROWS pan | o ops'
    short_help = 'F1 help | q quit | +/- speed | p pause | o ops'

    kpi_x = max(2, maxx - len(kpi_str) - 2)
    if kpi_x > 2 + len(help_str) + 1:
        safe_addstr(win, 2, 2, help_str[: maxx - 4], attr_for(state, 'DIM'))
        role = ops_tier_role(net_ot) if net_ot is not None else 'DIM'
        safe_addstr(win, 2, kpi_x, kpi_str[: maxx - kpi_x - 2], attr_for(state, role, bold=True))
    else:
        safe_addstr(win, 2, 2, short_help[: maxx - 4], attr_for(state, 'DIM'))
        role = ops_tier_role(net_ot) if net_ot is not None else 'DIM'
        safe_addstr(win, 3, 2, kpi_str[: maxx - 4], attr_for(state, role, bold=True))


def draw_fleet(win, state: GameState, now_t: float):
    win.erase()
    win.box()
    apply_win_bkgd(win)
    safe_addstr(win, 0, 2, ' fleet ', attr_for(state, 'TITLE'))
    safe_addstr(
        win,
        1,
        2,
        'ID  Model  Service      State   At/Edge             ETA(g) LastRev',
        attr_for(state, 'DIM'),
    )
    try:
        win.hline(2, 1, curses.ACS_HLINE, win.getmaxyx()[1] - 2)
    except curses.error:
        pass
    row = 3
    for t in sorted(state.trains, key=lambda x: x.id):
        if row >= win.getmaxyx()[0] - 1:
            break
        svc = (t.service_id or '-')[:11]
        where = t.at_node or '-'
        eta = '-'
        if t.state == 'RUN' and t.current_edge:
            where = t.current_edge
            eta_base = t.next_event_t if t.next_event_t else t.edge_arrive_t
            try:
                eta = f'{max(0, int(float(eta_base) - float(now_t)))}s'
            except Exception:
                eta = '??'
        elif t.state in ('DWELL', 'WAIT') and t.next_event_t:
            eta = f'{max(0, int(float(t.next_event_t) - float(now_t)))}s'
        line = f'{t.id:<3} {t.model_id:<5} {svc:<11} {t.state:<6} {where:<18} {eta:<6} {fmt_money(t.last_revenue):>8}'
        safe_addstr(win, row, 2, line, attr_for(state, train_role(t)))
        row += 1


def draw_pinned(win, state: GameState, ops_lines: list[str], now_t: float):
    win.erase()
    win.box()
    apply_win_bkgd(win)
    safe_addstr(win, 0, 2, ' pinned ', attr_for(state, 'TITLE'))
    lines = (
        state.pinned_override_lines
        if (state.pinned_override_lines and float(now_t) < float(state.pinned_override_until_game))
        else ops_lines
    )
    maxy, maxx = win.getmaxyx()
    y = 1
    for ln in lines[: maxy - 2]:
        safe_addstr(win, y, 2, ln[: maxx - 4], attr_for(state, 'HEADER'))
        y += 1
        if y >= maxy - 1:
            break


def draw_log(win, state: GameState):
    win.erase()
    win.box()
    apply_win_bkgd(win)
    safe_addstr(win, 0, 2, ' log ', attr_for(state, 'TITLE'))
    maxy, maxx = win.getmaxyx()
    lines = state.msg_log[-(maxy - 2) :]
    for i, ln in enumerate(lines, start=1):
        if i >= maxy - 1:
            break
        safe_addstr(win, i, 2, ln[: maxx - 4], attr_for(state, 'HEADER'))


def draw_input(win, buf: str, state: GameState):
    win.erase()
    win.box()
    apply_win_bkgd(win)
    maxy, maxx = win.getmaxyx()
    text = '> ' + buf
    safe_addstr(win, 1, 2, text[: maxx - 4], attr_for(state, 'HEADER'))
    try:
        win.move(1, min(maxx - 3, 2 + len(text)))
    except curses.error:
        pass


def draw_popup(stdscr, text: str):
    lines = text.splitlines()
    maxy, maxx = stdscr.getmaxyx()
    h = min(maxy - 2, len(lines) + 4)
    w = min(maxx - 2, max((len(line) for line in lines), default=20) + 4)
    y0 = max(1, (maxy - h) // 2)
    x0 = max(1, (maxx - w) // 2)
    win = curses.newwin(h, w, y0, x0)
    apply_win_bkgd(win)
    win.erase()
    win.box()
    safe_addstr(win, 0, 2, ' popup ', curses.A_BOLD)
    visible = max(1, h - 4)
    for i, ln in enumerate(lines[:visible]):
        safe_addstr(win, 2 + i, 2, ln[: w - 4])
    safe_addstr(win, h - 2, 2, 'Press any key')
    win.refresh()
    stdscr.nodelay(False)
    stdscr.getch()
    stdscr.nodelay(True)


def draw_map(win, world: World, state: GameState, blocks: dict[str, dict], now_t: float):
    win.erase()
    win.box()
    apply_win_bkgd(win)
    safe_addstr(win, 0, 2, f' map zoom {state.view_zoom}x ', attr_for(state, 'TITLE'))
    maxy, maxx = win.getmaxyx()
    disc_edges = set(state.discovered_edges)
    disc_nodes = set(state.discovered_nodes)

    for eid in disc_edges:
        e = world.edges.get(eid)
        if not e:
            continue
        blk = blocks.get(eid)
        occ = False
        if blk:
            occ = (
                (blk.get('occ') is not None)
                if blk.get('mode') == 'single'
                else (blk.get('occ_fwd') is not None or blk.get('occ_rev') is not None)
            )

        base_ch = '-' if e.tracks <= 1 else '='
        ch = '#' if occ else base_ch
        attr = attr_for(state, 'TRACK_OCC' if occ else 'TRACK')

        pts = dogleg_points_for_edge(world, e)
        if not pts:
            continue
        (wx0, wy0), (wxe, wye), (wx1, wy1) = pts
        x0, y0 = viewport_transform(state, wx0, wy0, maxx, maxy)
        xe, ye = viewport_transform(state, wxe, wye, maxx, maxy)
        x1, y1 = viewport_transform(state, wx1, wy1, maxx, maxy)

        draw_line_segment(win, x0, y0, xe, ye, ch, attr)
        draw_line_segment(win, xe, ye, x1, y1, ch, attr)

    for nid in disc_nodes:
        if nid not in world.panel_pos:
            continue
        n = world.nodes.get(nid)
        if not n:
            continue
        wx, wy = world.panel_pos[nid]
        x, y = viewport_transform(state, wx, wy, maxx, maxy)
        if not in_bounds(x, y, maxx, maxy):
            continue
        if n.kind == 'JUNCTION':
            glyph, role = '+', 'JUNCTION'
        else:
            glyph, role = ('O', 'STATION_MAJOR') if n.major else ('o', 'STATION_MINOR')
        safe_addch(win, y, x, glyph, attr_for(state, role, bold=n.major))
        if in_bounds(x - 1, y - 1, maxx, maxy):
            lbl = label_for_node(nid, n.kind)
            safe_addstr(
                win,
                y - 1,
                max(1, x - 1),
                lbl,
                attr_for(state, 'DIM' if n.kind == 'JUNCTION' else role),
            )

    for t in state.trains:
        pos = estimate_train_world_pos(world, t, now_t)
        if not pos:
            continue
        wx, wy = pos
        x, y = viewport_transform(state, wx, wy, maxx, maxy)
        if not in_bounds(x, y, maxx, maxy):
            continue
        safe_addstr(win, y, x, f'{train_marker(t)}{t.id}', attr_for(state, train_role(t), bold=True))


# -----------------------------
# UI main loop
# -----------------------------

ZOOM_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
SPEED_STEPS = [1, 5, 10, 30, 60, 120, 300, 600]


def adjust_zoom(state: GameState, zoom_in: bool) -> None:
    cur = state.view_zoom
    idx = 0
    for i, s in enumerate(ZOOM_STEPS):
        if cur >= s:
            idx = i
    idx = min(len(ZOOM_STEPS) - 1, max(0, idx + (1 if zoom_in else -1)))
    state.view_zoom = float(ZOOM_STEPS[idx])


def pan_view(state: GameState, dx: float, dy: float) -> None:
    state.follow_train_id = None
    step = max(1.0, 5.0 / max(0.5, state.view_zoom))
    state.view_cx += dx * step
    state.view_cy += dy * step


def adjust_speed(state: GameState, up: bool) -> None:
    cur = state.time_scale
    idx = 0
    for i, s in enumerate(SPEED_STEPS):
        if cur >= s:
            idx = i
    idx = min(len(SPEED_STEPS) - 1, max(0, idx + (1 if up else -1)))
    state.time_scale = float(SPEED_STEPS[idx])
    state.paused = False


def ui_main(stdscr):
    curses.curs_set(1)
    stdscr.nodelay(True)
    stdscr.timeout(50)
    init_curses(stdscr)

    world = World()
    world.panel_pos = dict(PANEL_POS_DEFAULT)
    world.load_region_file(DEFAULT_REGION_ID)

    state = load_game() or new_game()
    init_theme_colors(state)

    if not state.trains:
        state.trains.append(Train(id=0, model_id='dmu'))
        state.next_train_id = 1

    blocks: dict[str, dict] = {}
    rebuild_blocks(world, state, blocks)

    # offline progress
    real_now = time.time()
    dt_real = max(0.0, real_now - state.last_real_time)
    state.last_real_time = real_now
    if not state.paused and dt_real > 1.0:
        state.game_time += dt_real * state.time_scale
        log_event(
            state,
            f'Offline: +{int(dt_real)}s real ({int(dt_real * state.time_scale)}s game)',
            level='important',
        )

    cmd_buf = ''

    while True:
        real_now = time.time()
        dt_real = max(0.0, real_now - state.last_real_time)
        state.last_real_time = real_now
        if not state.paused and state.time_scale > 0:
            state.game_time += dt_real * state.time_scale
        now_t = state.game_time

        services = build_available_services(world, state)
        net_ot = network_ontime_pct(state, services)
        net_hw = network_headway_health_pct(state, services)
        ops_lines = ops_dashboard_lines(state, services, now_t)

        if state.follow_train_id is not None:
            ft = next((t for t in state.trains if t.id == state.follow_train_id), None)
            if ft:
                p = estimate_train_world_pos(world, ft, now_t)
                if p:
                    state.view_cx, state.view_cy = p

        for tr in state.trains:
            if tr.at_node is None and state.home:
                tr.at_node = state.home

        simulate(world, state, services, blocks, now_t)

        maxy, maxx = stdscr.getmaxyx()
        header_h = 5
        input_h = 3
        body_h = maxy - header_h - input_h

        map_w = int(maxx * 0.55) if state.ui_show_map else 0
        left_w = maxx - map_w
        left_top_h = int(body_h * 0.55)
        left_bot_h = body_h - left_top_h
        pinned_h = min(10, max(4, left_bot_h // 2))

        header = stdscr.derwin(header_h, maxx, 0, 0)
        fleet_win = stdscr.derwin(left_top_h, left_w, header_h, 0)
        pinned_win = stdscr.derwin(pinned_h, left_w, header_h + left_top_h, 0)
        log_win = stdscr.derwin(left_bot_h - pinned_h, left_w, header_h + left_top_h + pinned_h, 0)
        map_win = stdscr.derwin(body_h, map_w, header_h, left_w) if map_w else None
        input_win = stdscr.derwin(input_h, maxx, header_h + body_h, 0)

        apply_win_bkgd(header)
        apply_win_bkgd(fleet_win)
        apply_win_bkgd(pinned_win)
        apply_win_bkgd(log_win)
        apply_win_bkgd(input_win)
        if map_win:
            apply_win_bkgd(map_win)

        draw_header(header, state, net_ot, net_hw)
        draw_fleet(fleet_win, state, now_t)
        draw_pinned(pinned_win, state, ops_lines, now_t)
        draw_log(log_win, state)
        if map_win:
            draw_map(map_win, world, state, blocks, now_t)
        draw_input(input_win, cmd_buf, state)

        header.noutrefresh()
        fleet_win.noutrefresh()
        pinned_win.noutrefresh()
        log_win.noutrefresh()
        input_win.noutrefresh()
        if map_win:
            map_win.noutrefresh()
        curses.doupdate()

        ch = stdscr.getch()
        if ch == -1:
            continue

        if ch == curses.KEY_RESIZE:
            stdscr.erase()
            stdscr.refresh()
            continue

        if ch in (ord('q'), ord('Q')):
            save_game(state)
            break

        if ch == curses.KEY_F1:
            draw_popup(stdscr, '\n'.join(HELP_LINES))
            stdscr.erase()
            stdscr.refresh()
            continue

        if cmd_buf == '' and ch in (ord('o'), ord('O')):
            draw_popup(stdscr, build_ops_report(state, services, now_t))
            stdscr.erase()
            stdscr.refresh()
            continue

        CTRL_P, CTRL_N = 16, 14
        if ch == CTRL_P or (ch == curses.KEY_UP and cmd_buf != ''):
            if state.cmd_history:
                if state.cmd_hist_idx == -1:
                    state.cmd_hist_idx = len(state.cmd_history) - 1
                else:
                    state.cmd_hist_idx = max(0, state.cmd_hist_idx - 1)
                cmd_buf = state.cmd_history[state.cmd_hist_idx]
            continue

        if ch == CTRL_N or (ch == curses.KEY_DOWN and cmd_buf != ''):
            if state.cmd_history and state.cmd_hist_idx != -1:
                state.cmd_hist_idx += 1
                if state.cmd_hist_idx >= len(state.cmd_history):
                    state.cmd_hist_idx = -1
                    cmd_buf = ''
                else:
                    cmd_buf = state.cmd_history[state.cmd_hist_idx]
            continue

        if cmd_buf == '':
            if ch == ord('+'):
                adjust_speed(state, up=True)
                log_msg(state, f'Speed set to {state.time_scale:.0f}x')
                continue
            if ch == ord('-'):
                adjust_speed(state, up=False)
                log_msg(state, f'Speed set to {state.time_scale:.0f}x')
                continue
            if ch in (ord('p'), ord('P')):
                state.paused = not state.paused
                log_msg(state, 'Paused.' if state.paused else f'Resumed at {state.time_scale:.0f}x')
                continue
            if ch == ord('['):
                adjust_zoom(state, zoom_in=False)
                continue
            if ch == ord(']'):
                adjust_zoom(state, zoom_in=True)
                continue
            if ch == ord('f'):
                state.follow_train_id = 0 if state.follow_train_id is None else None
                continue
            if ch == ord('F'):
                state.follow_train_id = None
                continue
            if ch == curses.KEY_LEFT:
                pan_view(state, -1, 0)
                continue
            if ch == curses.KEY_RIGHT:
                pan_view(state, 1, 0)
                continue
            if ch == curses.KEY_UP:
                pan_view(state, 0, -1)
                continue
            if ch == curses.KEY_DOWN:
                pan_view(state, 0, 1)
                continue

        if ch in (curses.KEY_ENTER, 10, 13):
            push_history(state, cmd_buf)
            msg = handle_command(world, state, services, blocks, cmd_buf, now_t)
            if msg:
                if msg.count('\n') >= 3:
                    draw_popup(stdscr, msg)
                    stdscr.erase()
                    stdscr.refresh()
                else:
                    log_msg(state, msg)
            cmd_buf = ''
            state.cmd_hist_idx = -1
            continue

        if ch in (curses.KEY_BACKSPACE, 127, 8):
            cmd_buf = cmd_buf[:-1]
            state.cmd_hist_idx = -1
            continue

        if 32 <= ch <= 126:
            cmd_buf += chr(ch)
            state.cmd_hist_idx = -1
            continue


def main():
    curses.wrapper(ui_main)


if __name__ == '__main__':
    main()

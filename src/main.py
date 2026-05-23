"""
DEFRAG.EXE - Windows 95 styled defrag clicker/idler

Single-file prototype. Major systems:
  - GameState dataclass with JSON save/load (3 save slots, autosave)
  - Real click rate via sliding window; auto-clicker nodes add virtual clicks
  - Shatter-on-clean fragment tiering (sys -> media -> doc -> temp -> gone)
  - Scaling prestige (multiplicative legacy + global mult per prestige)
  - 6 disks C: through H: with hardness curve
  - ~140 skill nodes across Manual/Click/Auto/Filesystem branches
  - ~26 legacy (prestige) nodes
  - Win95 chrome: beveled controls, navy titlebars, taskbar, MS Sans-ish font

Entry: python src/main.py
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import pygame

# ============================================================================
# WINDOW / LAYOUT
# ============================================================================

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 768  # bumped to give taskbar room

TITLEBAR_H = 22
WINDOW_BORDER = 3
MENUBAR_H = 22
TASKBAR_H = 30
DESKTOP_TOP = 0
DESKTOP_BOTTOM = WINDOW_HEIGHT - TASKBAR_H

GRID_COLS = 48
GRID_ROWS = 24
CELL_SIZE = 12
TOTAL_CELLS = GRID_COLS * GRID_ROWS

# ============================================================================
# WIN95 COLOR PALETTE
# ============================================================================

W95_DESKTOP        = (0, 128, 128)     # teal desktop
W95_FACE           = (192, 192, 192)   # button/panel face
W95_FACE_DIM       = (160, 160, 160)
W95_LIGHT          = (255, 255, 255)   # bevel highlight (top/left raised)
W95_SHADOW         = (128, 128, 128)   # bevel shadow (bottom/right raised)
W95_DARK           = (0, 0, 0)         # outer dark
W95_TITLE_ACTIVE   = (0, 0, 128)       # navy active titlebar
W95_TITLE_GRAD     = (16, 56, 200)     # titlebar gradient end
W95_TITLE_INACTIVE = (128, 128, 128)
W95_TITLE_TEXT     = (255, 255, 255)
W95_TEXT           = (0, 0, 0)
W95_TEXT_DIM       = (96, 96, 96)
W95_TEXT_DISABLED  = (128, 128, 128)
W95_SELECT_BG      = (0, 0, 128)
W95_SELECT_TEXT    = (255, 255, 255)
W95_LINK           = (0, 0, 192)

# Defrag visualization (inside the defrag window)
# Win95/98 defrag palette — pure VGA-16 primaries against the classic navy field.
# Cell colors map to file-type cost (cheap → bright "data" colors, heavy → danger reds).
DEFRAG_FIELD       = (0,   0,   128)   # #000080 — VGA navy (classic defrag background)
DEFRAG_FRAME       = (0,   0,   0)     # #000000 — black frame edge
DEFRAG_GOOD        = (0,   255, 255)   # #00FFFF — VGA cyan (optimized clusters)
DEFRAG_READING     = (255, 255, 0)     # #FFFF00 — VGA yellow (read activity)
DEFRAG_WRITING     = (255, 0,   0)     # #FF0000 — VGA red   (write activity)
FRAG_TEMP          = (255, 255, 0)     # #FFFF00 — VGA yellow (cheapest data)
FRAG_DOC           = (0,   255, 0)     # #00FF00 — VGA green  (regular data)
FRAG_MEDIA         = (255, 0,   255)   # #FF00FF — VGA magenta (heavy data)
FRAG_SYS           = (255, 0,   0)     # #FF0000 — VGA red    (system / dangerous)
# Win95 light grey (#C0C0C0) used for the cell-change activity outline
HIGHLIGHT_BORDER   = (192, 192, 192)

# ============================================================================
# SIMULATION BASE CONSTANTS
# ============================================================================

BASE_M  = 8.0      # power per click (tuned so a dedicated first-time clicker on C: lands near 90% progress)
BASE_R  = 3.0      # max manual clicks/sec accepted by the cap
BASE_A  = 1.5      # passive defrag rate; *zeroed* until any Auto node bought (see recompute_stats)
BASE_E  = 1.0
BASE_FR = 0.0
BASE_AUTOCLICK = 0.0  # virtual clicks/sec from auto-clicker nodes

BASE_TYPE_COSTS = {'temp': 0.6, 'doc': 1.0, 'media': 1.8, 'sys': 2.5}

CLICK_WINDOW = 0.6                 # seconds for the CPS sliding window
COMPLETION_FRAG_PERCENT = 1.5      # session wins when <= this % of cells remain fragmented (lenient buffer for endgame)

# Starter DP for a brand new game so the player can buy a node or two before the first attempt
NEW_GAME_STARTER_DP = 8

# ============================================================================
# DISK DEFINITIONS
# ============================================================================

DISK_LETTERS = "CDEFGHIJKLMNOPQRSTUVWXYZ"  # 24 disks


def _generate_disks() -> dict:
    """Build DISK specs for C: through Z:.

    Boss-disk pattern: H:/N:/R:/V: are ~2.5x hardness jumps from the previous disk;
    Z: is the final boss. Disks between bosses grow at ~1.4-1.5x as plateaus.
    The S-curve in player power should produce the 'speedup-then-plateau' rhythm
    when crossed with this hardness curve."""
    # Hand-tuned hardness, start_frag, timer per disk (replaces the smooth growth)
    # (order, timer, hardness, start_frag, write, capacity_gb)
    disk_specs = [
        (1,  15,       1.0, 0.40,  4.0,         16),  # C:
        (2,  22,       2.2, 0.45,  5.5,         32),  # D:
        (3,  30,       4.5, 0.55,  7.5,         64),  # E:
        (4,  42,       9.0, 0.60, 10.0,        128),  # F:
        (5,  60,      18.0, 0.65, 14.0,        256),  # G:
        (6,  90,      50.0, 0.70, 18.0,        512),  # H: ← BOSS 1
        (7,  118,     75.0, 0.71, 19.0,       1024),  # I:
        (8,  146,    110.0, 0.72, 20.0,       2048),  # J:
        (9,  174,    160.0, 0.73, 21.0,       4096),  # K:
        (10, 202,    230.0, 0.74, 22.0,       8192),  # L:
        (11, 230,    330.0, 0.75, 23.0,      16384),  # M:
        (12, 258,    800.0, 0.76, 26.0,      32768),  # N: ← BOSS 2
        (13, 286,   1100.0, 0.77, 28.0,      65536),  # O:
        (14, 314,   1550.0, 0.78, 30.0,     131072),  # P:
        (15, 342,   2200.0, 0.79, 32.0,     262144),  # Q:
        (16, 370,   5500.0, 0.80, 36.0,     524288),  # R: ← BOSS 3
        (17, 398,   7800.0, 0.81, 39.0,    1048576),  # S:
        (18, 426,  11000.0, 0.82, 42.0,    2097152),  # T:
        (19, 450,  15500.0, 0.83, 45.0,    4194304),  # U:
        (20, 450,  40000.0, 0.84, 50.0,    8388608),  # V: ← BOSS 4
        (21, 450,  55000.0, 0.85, 53.0,   16777216),  # W:
        (22, 450,  78000.0, 0.85, 56.0,   33554432),  # X:
        (23, 450, 110000.0, 0.85, 58.0,   67108864),  # Y:
        (24, 450, 280000.0, 0.85, 60.0,  134217728),  # Z: ← FINAL BOSS
    ]

    disks = {}
    for i, letter in enumerate(DISK_LETTERS):
        order = i + 1
        key = letter + ":"
        _, timer, hardness, start_frag, write, capacity = disk_specs[order - 1]

        # File mix: interpolate from temp/doc-heavy (C:) to sys-heavy (Z:)
        t = (order - 1) / (len(DISK_LETTERS) - 1)
        raw_mix = {
            'temp':  max(0.02, 0.60 - 0.58 * t),
            'doc':   max(0.06, 0.32 - 0.26 * t),
            'media': min(0.42, 0.06 + 0.32 * t),
            'sys':   min(0.70, 0.02 + 0.66 * t),
        }
        s = sum(raw_mix.values())
        mix = {k: round(v / s, 4) for k, v in raw_mix.items()}

        # Shatter chains scale with depth. Cascade chance values are sim-tuned (0.5x
        # the "natural" curve) so the shatter equilibrium on Z: stays just below the
        # win threshold once a player has maxed Inviolate + Containment FR.
        if order == 1:
            shatter = {'sys': ['media'], 'media': [], 'doc': [], 'temp': []}
            cascade = 0.0
        elif order == 2:
            shatter = {'sys': ['media'], 'media': ['doc'], 'doc': [], 'temp': []}
            cascade = 0.0
        elif order <= 4:
            shatter = {'sys': ['media'], 'media': ['doc'], 'doc': ['temp'], 'temp': []}
            cascade = 0.02 + (order - 3) * 0.02
        elif order <= 6:
            shatter = {'sys': ['media', 'media'], 'media': ['doc'], 'doc': ['temp'], 'temp': []}
            cascade = 0.05 + (order - 5) * 0.02
        elif order <= 10:
            shatter = {'sys': ['media', 'media'], 'media': ['doc', 'doc'], 'doc': ['temp'], 'temp': []}
            cascade = 0.09 + (order - 7) * 0.015
        elif order <= 16:
            shatter = {'sys': ['media', 'media'], 'media': ['doc', 'doc'], 'doc': ['temp', 'temp'], 'temp': []}
            cascade = 0.15 + (order - 11) * 0.01
        else:
            # Late disks (S:-Z:): sys -> 2 media (not 3) so maxed players can reach the
            # shatter equilibrium below threshold. Cascade still high enough to feel chaotic.
            shatter = {'sys': ['media', 'media'], 'media': ['doc', 'doc'], 'doc': ['temp', 'temp'], 'temp': []}
            cascade = min(0.32, 0.20 + (order - 17) * 0.01)

        disks[key] = {
            'label': key,
            'capacity_gb': capacity,
            'start_frag': round(start_frag, 3),
            'hardness': hardness,
            'write_intensity': round(write, 2),
            'base_timer': timer,
            'file_mix': mix,
            'shatter': shatter,
            'cascade_chance': round(cascade, 3),
        }
    return disks


DISKS = _generate_disks()
DISK_ORDER = {k: i + 1 for i, k in enumerate(d + ':' for d in DISK_LETTERS)}


def format_capacity(gb: int) -> str:
    """Human-readable capacity. 16 -> '16 GB', 1024 -> '1.00 TB', 1024 TB -> '1.00 PB', etc."""
    units = [(1024 ** 3, 'EB'), (1024 ** 2, 'PB'), (1024, 'TB'), (1, 'GB')]
    for div, unit in units:
        if gb >= div:
            val = gb / div
            if unit == 'GB' or val >= 100:
                return f"{val:.0f} {unit}"
            if val >= 10:
                return f"{val:.1f} {unit}"
            return f"{val:.2f} {unit}"
    return f"{gb} GB"


# ============================================================================
# SKILL TREE GENERATOR
# ============================================================================

# Per-tier cost multiplier applied to fixed skill nodes. Late-tier nodes are
# many times more expensive so they actually consume late-game DP wealth.
TIER_COST_MULT = {
    1: 1.0, 2: 1.0,
    3: 2.0, 4: 2.0,
    5: 5.0,
    6: 15.0,
    7: 50.0,
    8: 200.0,
    9: 600.0,
    10: 2000.0,
}


def build_skill_nodes():
    """Build the per-life skill node graph (~140 nodes across 4 branches)."""
    nodes = []
    counter = [0]

    def mkid(prefix):
        counter[0] += 1
        return f"{prefix}_{counter[0]:03d}"

    def line(branch, family, prefix, steps, base_cost, base_tier):
        """steps: list of (suffix, desc, tdelta, cost_mult, effect_dict)"""
        ids = []
        for i, (suffix, desc, tdelta, cmult, eff) in enumerate(steps):
            nid = mkid(prefix)
            tier = max(1, base_tier + tdelta)
            tier_mult = TIER_COST_MULT.get(tier, 1.0)
            raw_cost = base_cost * cmult * (1 + i * 0.22) * tier_mult
            # Clamp floor to 3, no upper cap (tier 8 nodes are intentionally pricey)
            cost = max(3, int(raw_cost))
            prereqs = [ids[-1]] if ids else []
            nodes.append({
                'id': nid,
                'name': f"{family} {suffix}",
                'desc': desc,
                'branch': branch,
                'tier': tier,
                'cost': cost,
                'effect': eff,
                'prereqs': prereqs,
            })
            ids.append(nid)
        return ids

    # ====== MANUAL (~36 nodes) ======
    power_ids = line('manual', 'Power', 'mpow', [
        ('I',   '+3.2% Manual Power (M)', 0, 1.0, {'type': 'M', 'value': 0.032}),
        ('II',  '+3.0% Manual Power',     0, 1.15,{'type': 'M', 'value': 0.030}),
        ('III', '+2.8% Manual Power',     1, 1.30,{'type': 'M', 'value': 0.028}),
        ('IV',  '+2.6% Manual Power',     1, 1.45,{'type': 'M', 'value': 0.026}),
        ('V',   '+2.4% Manual Power',     2, 1.60,{'type': 'M', 'value': 0.024}),
        ('VI',  '+2.2% Manual Power',     3, 1.78,{'type': 'M', 'value': 0.022}),
    ], base_cost=5, base_tier=1)
    burst_ids = line('manual', 'Burst', 'mbst', [
        ('I',   '+4.5% M (heavy)',  1, 1.4, {'type': 'M', 'value': 0.045}),
        ('II',  '+4.0% M (heavy)',  2, 1.6, {'type': 'M', 'value': 0.040}),
        ('III', '+3.5% M (heavy)',  3, 1.8, {'type': 'M', 'value': 0.035}),
    ], base_cost=10, base_tier=2)
    focus_ids = line('manual', 'Focus', 'mfoc', [
        ('I',   '+5% M when frag>55%', 1, 1.1, {'type': 'M_high', 'value': 0.05}),
        ('II',  '+4% M when frag>55%', 2, 1.3, {'type': 'M_high', 'value': 0.04}),
        ('III', '+3% M when frag>55%', 3, 1.55,{'type': 'M_high', 'value': 0.03}),
    ], base_cost=7, base_tier=2)
    finish_ids = line('manual', 'Finish', 'mfin', [
        ('I',   '+6% M when frag<25%', 1, 1.1, {'type': 'M_low', 'value': 0.06}),
        ('II',  '+5% M when frag<25%', 2, 1.3, {'type': 'M_low', 'value': 0.05}),
        ('III', '+4% M when frag<25%', 3, 1.55,{'type': 'M_low', 'value': 0.04}),
    ], base_cost=8, base_tier=2)
    crit_ids = line('manual', 'Crit', 'mcrt', [
        ('I',   '+3% chance: click is 2x', 1, 1.2, {'type': 'crit_chance', 'value': 0.03}),
        ('II',  '+3% crit chance',         2, 1.4, {'type': 'crit_chance', 'value': 0.03}),
        ('III', '+2% crit chance + 0.5x mag', 3, 1.6, {'type': 'crit_chance', 'value': 0.02}),
    ], base_cost=12, base_tier=2)
    line('manual', 'TempSpec', 'mtmp', [
        ('I',   '+22% M vs Temp files',  0, 1.0, {'type': 'file_power', 'target': 'temp', 'mult': 1.22}),
        ('II',  '+18% M vs Temp',        1, 1.2, {'type': 'file_power', 'target': 'temp', 'mult': 1.18}),
        ('III', '+15% M vs Temp',        2, 1.4, {'type': 'file_power', 'target': 'temp', 'mult': 1.15}),
    ], base_cost=5, base_tier=1)
    line('manual', 'DocSpec', 'mdoc', [
        ('I',   '+16% M vs Documents',   0, 1.1, {'type': 'file_power', 'target': 'doc', 'mult': 1.16}),
        ('II',  '+13% M vs Documents',   1, 1.3, {'type': 'file_power', 'target': 'doc', 'mult': 1.13}),
        ('III', '+11% M vs Documents',   2, 1.5, {'type': 'file_power', 'target': 'doc', 'mult': 1.11}),
    ], base_cost=6, base_tier=1)
    line('manual', 'MediaSpec', 'mmed', [
        ('I',   '+18% M vs Media',       1, 1.0, {'type': 'file_power', 'target': 'media', 'mult': 1.18}),
        ('II',  '+15% M vs Media',       2, 1.25,{'type': 'file_power', 'target': 'media', 'mult': 1.15}),
        ('III', '+12% M vs Media',       3, 1.45,{'type': 'file_power', 'target': 'media', 'mult': 1.12}),
    ], base_cost=8, base_tier=1)
    line('manual', 'SysSpec', 'msys', [
        ('I',   '+14% M vs System',      2, 1.15,{'type': 'file_power', 'target': 'sys', 'mult': 1.14}),
        ('II',  '+11% M vs System',      3, 1.35,{'type': 'file_power', 'target': 'sys', 'mult': 1.11}),
        ('III', '+9% M vs System',       4, 1.55,{'type': 'file_power', 'target': 'sys', 'mult': 1.09}),
    ], base_cost=9, base_tier=2)
    rhythm_ids = line('manual', 'Rhythm', 'mrhy', [
        ('I',   '+4% M sustained',  1, 1.1, {'type': 'M', 'value': 0.04}),
        ('II',  '+3.5% M sustained',2, 1.35,{'type': 'M', 'value': 0.035}),
        ('III', '+3% M sustained',  3, 1.55,{'type': 'M', 'value': 0.03}),
    ], base_cost=8, base_tier=2)

    # ====== CLICK (~32 nodes) - click rate cap + auto-clickers + click multipliers ======
    rate_ids = line('click', 'Rate', 'crat', [
        ('I',   '+0.4 max CPS',  0, 1.0, {'type': 'R', 'value': 0.4}),
        ('II',  '+0.5 max CPS',  0, 1.15,{'type': 'R', 'value': 0.5}),
        ('III', '+0.6 max CPS',  1, 1.30,{'type': 'R', 'value': 0.6}),
        ('IV',  '+0.7 max CPS',  1, 1.45,{'type': 'R', 'value': 0.7}),
        ('V',   '+0.8 max CPS',  2, 1.60,{'type': 'R', 'value': 0.8}),
        ('VI',  '+1.0 max CPS',  3, 1.80,{'type': 'R', 'value': 1.0}),
    ], base_cost=4, base_tier=1)
    line('click', 'Sustain', 'csus', [
        ('I',   '+0.4 CPS cap when sustained',  1, 1.2, {'type': 'R', 'value': 0.4}),
        ('II',  '+0.5 CPS cap when sustained',  2, 1.4, {'type': 'R', 'value': 0.5}),
    ], base_cost=7, base_tier=2)
    macro_ids = line('click', 'Macro Recorder', 'cmac', [
        ('I',   '+0.5 virtual clicks/sec',  0, 1.0, {'type': 'auto_click', 'value': 0.5}),
        ('II',  '+0.8 virtual clicks/sec',  1, 1.2, {'type': 'auto_click', 'value': 0.8}),
        ('III', '+1.3 virtual clicks/sec',  1, 1.4, {'type': 'auto_click', 'value': 1.3}),
    ], base_cost=6, base_tier=1)
    line('click', 'Script Engine', 'cscr', [
        ('I',   '+1.5 virtual clicks/sec',  2, 1.4, {'type': 'auto_click', 'value': 1.5}),
        ('II',  '+2.5 virtual clicks/sec',  2, 1.7, {'type': 'auto_click', 'value': 2.5}),
        ('III', '+4.0 virtual clicks/sec',  3, 2.0, {'type': 'auto_click', 'value': 4.0}),
    ], base_cost=14, base_tier=2)
    line('click', 'Bot Farm', 'cbot', [
        ('I',   '+7 virtual clicks/sec',   3, 1.6, {'type': 'auto_click', 'value': 7.0}),
        ('II',  '+12 virtual clicks/sec',  3, 1.9, {'type': 'auto_click', 'value': 12.0}),
        ('III', '+18 virtual clicks/sec',  4, 2.2, {'type': 'auto_click', 'value': 18.0}),
    ], base_cost=24, base_tier=3)
    line('click', 'AI Clicker', 'cai_', [
        ('I',   '+28 virtual clicks/sec',  4, 1.8, {'type': 'auto_click', 'value': 28.0}),
        ('II',  '+45 virtual clicks/sec',  4, 2.1, {'type': 'auto_click', 'value': 45.0}),
        ('III', '+70 virtual clicks/sec',  5, 2.5, {'type': 'auto_click', 'value': 70.0}),
    ], base_cost=40, base_tier=4)
    line('click', 'Botnet', 'cnet', [
        ('I',   '+120 virtual clicks/sec', 5, 2.2, {'type': 'auto_click', 'value': 120.0}),
        ('II',  '+200 virtual clicks/sec', 5, 2.6, {'type': 'auto_click', 'value': 200.0}),
    ], base_cost=70, base_tier=5)
    line('click', 'Multi', 'cmlt', [
        ('I',   'Each click counts as 1.1', 1, 1.3, {'type': 'click_multi', 'value': 0.10}),
        ('II',  'Each click counts as 1.1', 2, 1.5, {'type': 'click_multi', 'value': 0.10}),
        ('III', 'Each click counts as 1.1', 3, 1.7, {'type': 'click_multi', 'value': 0.10}),
        ('IV',  'Each click counts as 1.1', 4, 1.9, {'type': 'click_multi', 'value': 0.10}),
    ], base_cost=18, base_tier=2)

    # ====== AUTO (~32 nodes) - passive defrag ======
    thru_ids = line('auto', 'Throughput', 'athr', [
        ('I',   '+4.0% Auto Speed (A)', 0, 1.0, {'type': 'A', 'value': 0.040}),
        ('II',  '+3.6% Auto Speed',     0, 1.15,{'type': 'A', 'value': 0.036}),
        ('III', '+3.2% Auto Speed',     1, 1.30,{'type': 'A', 'value': 0.032}),
        ('IV',  '+3.0% Auto Speed',     1, 1.45,{'type': 'A', 'value': 0.030}),
        ('V',   '+2.7% Auto Speed',     2, 1.60,{'type': 'A', 'value': 0.027}),
        ('VI',  '+2.4% Auto Speed',     3, 1.80,{'type': 'A', 'value': 0.024}),
    ], base_cost=5, base_tier=1)
    line('auto', 'A-Eff', 'aeff', [
        ('I',   '+2.8% Efficiency',     0, 1.05,{'type': 'E', 'value': 0.028}),
        ('II',  '+2.5% Efficiency',     1, 1.22,{'type': 'E', 'value': 0.025}),
        ('III', '+2.3% Efficiency',     2, 1.38,{'type': 'E', 'value': 0.023}),
        ('IV',  '+2.1% Efficiency',     3, 1.55,{'type': 'E', 'value': 0.021}),
    ], base_cost=6, base_tier=1)
    resist_ids = line('auto', 'Resist', 'ares', [
        ('I',   '+3.5% Frag Resistance',0, 1.0, {'type': 'FR', 'value': 0.035}),
        ('II',  '+3.0% FR',             0, 1.18,{'type': 'FR', 'value': 0.030}),
        ('III', '+2.7% FR',             1, 1.32,{'type': 'FR', 'value': 0.027}),
        ('IV',  '+2.4% FR',             2, 1.48,{'type': 'FR', 'value': 0.024}),
        ('V',   '+2.2% FR',             3, 1.65,{'type': 'FR', 'value': 0.022}),
    ], base_cost=6, base_tier=1)
    idle_ids = line('auto', 'Idle', 'aidl', [
        ('I',   '+22% A while idle',    0, 1.0, {'type': 'A_idle', 'value': 0.22}),
        ('II',  '+18% A idle bonus',    1, 1.2, {'type': 'A_idle', 'value': 0.18}),
        ('III', '+15% A during idle',   2, 1.35,{'type': 'A_idle', 'value': 0.15}),
        ('IV',  '+12% A idle (deep)',   3, 1.5, {'type': 'A_idle', 'value': 0.12}),
    ], base_cost=7, base_tier=1)
    line('auto', 'TempSweep', 'atms', [
        ('I',   '+25% A vs Temp',       0, 1.0, {'type': 'file_power', 'target': 'temp', 'mult': 1.25}),
        ('II',  '+20% A vs Temp',       1, 1.25,{'type': 'file_power', 'target': 'temp', 'mult': 1.20}),
    ], base_cost=5, base_tier=1)
    line('auto', 'MediaMover', 'amed', [
        ('I',   '+18% A vs Media',      1, 1.15,{'type': 'file_power', 'target': 'media', 'mult': 1.18}),
        ('II',  '+15% A vs Media',      2, 1.4, {'type': 'file_power', 'target': 'media', 'mult': 1.15}),
        ('III', '+12% A vs Media',      3, 1.55,{'type': 'file_power', 'target': 'media', 'mult': 1.12}),
    ], base_cost=7, base_tier=1)
    line('auto', 'SysCruncher', 'asys', [
        ('I',   '+16% A vs System',     2, 1.2, {'type': 'file_power', 'target': 'sys', 'mult': 1.16}),
        ('II',  '+13% A vs System',     3, 1.45,{'type': 'file_power', 'target': 'sys', 'mult': 1.13}),
    ], base_cost=10, base_tier=2)
    line('auto', 'Finisher', 'afin', [
        ('I',   '+14% A when frag<25%', 1, 1.2, {'type': 'A_low', 'value': 0.14}),
        ('II',  '+11% A endgame',       2, 1.4, {'type': 'A_low', 'value': 0.11}),
        ('III', '+9% A endgame',        3, 1.6, {'type': 'A_low', 'value': 0.09}),
    ], base_cost=8, base_tier=2)
    line('auto', 'AMSyn', 'aams', [
        ('I',   '+6% M on auto-cleaned',1, 1.1, {'type': 'M', 'value': 0.06}),
        ('II',  '+5% M when A strong',  2, 1.3, {'type': 'M', 'value': 0.05}),
        ('III', '+4% hybrid synergy',   3, 1.5, {'type': 'M', 'value': 0.04}),
    ], base_cost=8, base_tier=2)

    # ====== FILESYSTEM (~40 nodes) - costs, shatter mastery, conditions, time, hybrid ======
    line('fs', 'TempCost', 'ftmc', [
        ('I',   'Temp 12% cheaper',     0, 1.0, {'type': 'file_cost', 'target': 'temp', 'reduce': 0.12}),
        ('II',  'Temp 10% cheaper',     0, 1.2, {'type': 'file_cost', 'target': 'temp', 'reduce': 0.10}),
        ('III', 'Temp 9% cheaper',      1, 1.4, {'type': 'file_cost', 'target': 'temp', 'reduce': 0.09}),
    ], base_cost=5, base_tier=1)
    line('fs', 'DocCost', 'fdoc', [
        ('I',   'Docs 9% cheaper',      0, 1.1, {'type': 'file_cost', 'target': 'doc', 'reduce': 0.09}),
        ('II',  'Docs 8% cheaper',      1, 1.3, {'type': 'file_cost', 'target': 'doc', 'reduce': 0.08}),
        ('III', 'Docs 7% cheaper',      2, 1.5, {'type': 'file_cost', 'target': 'doc', 'reduce': 0.07}),
    ], base_cost=6, base_tier=1)
    line('fs', 'MediaCost', 'fmed', [
        ('I',   'Media 11% cheaper',    1, 1.0, {'type': 'file_cost', 'target': 'media', 'reduce': 0.11}),
        ('II',  'Media 9% cheaper',     2, 1.25,{'type': 'file_cost', 'target': 'media', 'reduce': 0.09}),
        ('III', 'Media 8% cheaper',     3, 1.45,{'type': 'file_cost', 'target': 'media', 'reduce': 0.08}),
    ], base_cost=7, base_tier=1)
    line('fs', 'SysCost', 'fsys', [
        ('I',   'System 8% cheaper',    2, 1.15,{'type': 'file_cost', 'target': 'sys', 'reduce': 0.08}),
        ('II',  'System 7% cheaper',    3, 1.35,{'type': 'file_cost', 'target': 'sys', 'reduce': 0.07}),
        ('III', 'System 6% cheaper',    4, 1.55,{'type': 'file_cost', 'target': 'sys', 'reduce': 0.06}),
    ], base_cost=9, base_tier=2)
    shatres_ids = line('fs', 'Containment', 'fcon', [
        ('I',   '-12% shatter children',1, 1.1, {'type': 'shatter_resist', 'value': 0.12}),
        ('II',  '-10% shatter children',2, 1.3, {'type': 'shatter_resist', 'value': 0.10}),
        ('III', '-8% shatter + -cascade',3, 1.5, {'type': 'shatter_resist', 'value': 0.08}),
        ('IV',  '-7% shatter + carry',  4, 1.7, {'type': 'shatter_resist', 'value': 0.07}),
    ], base_cost=10, base_tier=2)
    line('fs', 'Salvage', 'fsal', [
        ('I',   '+10% DP per shatter event', 2, 1.2, {'type': 'shatter_dp', 'value': 0.10}),
        ('II',  '+8% DP per shatter',        3, 1.4, {'type': 'shatter_dp', 'value': 0.08}),
        ('III', '+6% DP per shatter',        4, 1.6, {'type': 'shatter_dp', 'value': 0.06}),
    ], base_cost=12, base_tier=2)
    badsec_ids = line('fs', 'BadSec', 'fbad', [
        ('I',   'Bad sectors -20% penalty',  1, 1.1, {'type': 'E', 'value': 0.03}),
        ('II',  '+4% E bad sector handling', 2, 1.28,{'type': 'E', 'value': 0.025}),
        ('III', 'Skip bad sectors +FR',      3, 1.45,{'type': 'FR', 'value': 0.03}),
        ('IV',  'Forensic recovery +FR',     4, 1.65,{'type': 'FR', 'value': 0.025}),
    ], base_cost=8, base_tier=2)
    alloc_ids = line('fs', 'Alloc', 'falc', [
        ('I',   '+3.5% global E',       0, 1.15,{'type': 'E', 'value': 0.035}),
        ('II',  '+3.0% E + small FR',   1, 1.3, {'type': 'E', 'value': 0.030}),
        ('III', '+2.6% E + prealloc',   2, 1.48,{'type': 'E', 'value': 0.026}),
        ('IV',  '+2.3% perfect layout', 3, 1.62,{'type': 'E', 'value': 0.023}),
        ('V',   '+2.0% E (master)',     4, 1.78,{'type': 'E', 'value': 0.020}),
    ], base_cost=7, base_tier=1)
    hybrid_ids = line('fs', 'Hybrid', 'fhyb', [
        ('I',   '+5% M and +4% A',      1, 1.2, {'type': 'M', 'value': 0.05}),
        ('II',  '+4% M +4% A',          2, 1.38,{'type': 'M', 'value': 0.04}),
        ('III', '+3.5% all stats',      3, 1.55,{'type': 'E', 'value': 0.02}),
        ('IV',  '+2.5% all stats',      4, 1.75,{'type': 'M', 'value': 0.025}),
    ], base_cost=11, base_tier=2)
    cond_ids = line('fs', 'Cond', 'fcnd', [
        ('I',   '+6% power at frag>55%',1, 1.1, {'type': 'M_high', 'value': 0.06}),
        ('II',  '+5% A at frag<25%',    2, 1.32,{'type': 'A_low', 'value': 0.05}),
        ('III', '+4% FR write-heavy',   3, 1.48,{'type': 'FR', 'value': 0.04}),
    ], base_cost=8, base_tier=2)
    time_ids = line('fs', 'Time', 'ftim', [
        ('I',   '+8s timer (permanent)',  0, 1.0, {'type': 'time', 'value': 8}),
        ('II',  '+10s timer',             1, 1.25,{'type': 'time', 'value': 10}),
        ('III', '+14s timer',             1, 1.42,{'type': 'time', 'value': 14}),
        ('IV',  '+18s timer',             2, 1.60,{'type': 'time', 'value': 18}),
        ('V',   '+24s major maintenance', 3, 1.8, {'type': 'time', 'value': 24}),
        ('VI',  '+32s long-window',       4, 2.0, {'type': 'time', 'value': 32}),
    ], base_cost=8, base_tier=1)
    line('fs', 'LegacyPrep', 'flpr', [
        ('I',   '+2% FR first 25% of disk', 2, 1.2, {'type': 'FR', 'value': 0.02}),
        ('II',  '+E carry feel',            2, 1.4, {'type': 'E', 'value': 0.015}),
        ('III', '+FR institutional',        3, 1.6, {'type': 'FR', 'value': 0.025}),
    ], base_cost=12, base_tier=2)

    # ====== TIER 6-8 numerical extensions (gated by progress to N:/Q:/T:) ======
    # NOTE: in line(), final tier = base_tier + tdelta. So for tier 6-8 nodes with
    # base_tier=6, tdelta values are 0/1/2.
    line('manual', 'Power', 'mpow', [
        ('VII',  '+2.0% Manual Power', 0, 2.0, {'type': 'M', 'value': 0.020}),
        ('VIII', '+1.8% Manual Power', 1, 2.4, {'type': 'M', 'value': 0.018}),
        ('IX',   '+1.6% Manual Power', 2, 2.8, {'type': 'M', 'value': 0.016}),
    ], base_cost=14, base_tier=6)
    line('click', 'Rate', 'crat', [
        ('VII',  '+1.2 max CPS', 0, 2.0, {'type': 'R', 'value': 1.2}),
        ('VIII', '+1.5 max CPS', 1, 2.4, {'type': 'R', 'value': 1.5}),
    ], base_cost=14, base_tier=6)
    line('click', 'Mass Botnet', 'cmbn', [
        ('I',  '+400 virtual clicks/sec', 0, 3.0, {'type': 'auto_click', 'value': 400.0}),
        ('II', '+750 virtual clicks/sec', 1, 3.5, {'type': 'auto_click', 'value': 750.0}),
    ], base_cost=110, base_tier=7)
    line('auto', 'Throughput', 'athr', [
        ('VII',  '+2.2% Auto Speed', 0, 2.0, {'type': 'A', 'value': 0.022}),
        ('VIII', '+2.0% Auto Speed', 1, 2.4, {'type': 'A', 'value': 0.020}),
        ('IX',   '+1.8% Auto Speed', 2, 2.8, {'type': 'A', 'value': 0.018}),
    ], base_cost=14, base_tier=6)
    line('auto', 'A-Eff', 'aeff', [
        ('V',  '+1.9% Efficiency', 0, 2.0, {'type': 'E', 'value': 0.019}),
        ('VI', '+1.7% Efficiency', 1, 2.4, {'type': 'E', 'value': 0.017}),
    ], base_cost=14, base_tier=6)
    line('auto', 'Resist', 'ares', [
        ('VI', '+2.0% FR', 0, 2.0, {'type': 'FR', 'value': 0.020}),
        ('VII','+1.8% FR', 1, 2.4, {'type': 'FR', 'value': 0.018}),
    ], base_cost=14, base_tier=6)
    # Late-game heavy FR nodes — these are what let maxed players reach Z:'s shatter
    # equilibrium below threshold. Inviolate I-III span tier 7-8, totalling +32% FR.
    line('auto', 'Inviolate', 'ainv', [
        ('I',   '+12% Frag Resistance', 0, 3.0, {'type': 'FR', 'value': 0.12}),
        ('II',  '+10% Frag Resistance', 1, 3.5, {'type': 'FR', 'value': 0.10}),
        ('III', '+10% Frag Resistance', 1, 4.0, {'type': 'FR', 'value': 0.10}),
    ], base_cost=80, base_tier=7)
    line('fs', 'Containment', 'fcon2', [
        ('V',  '-8% shatter children',  0, 2.5, {'type': 'shatter_resist', 'value': 0.08}),
        ('VI', '-7% shatter children',  1, 3.0, {'type': 'shatter_resist', 'value': 0.07}),
        ('VII','-6% shatter children + master', 2, 3.5, {'type': 'shatter_resist', 'value': 0.06}),
    ], base_cost=50, base_tier=6)
    line('fs', 'Alloc', 'falc', [
        ('VI', '+1.8% global E', 0, 2.0, {'type': 'E', 'value': 0.018}),
        ('VII','+1.6% global E', 1, 2.4, {'type': 'E', 'value': 0.016}),
        ('VIII','+1.5% global E (master)', 2, 2.8, {'type': 'E', 'value': 0.015}),
    ], base_cost=14, base_tier=6)
    line('fs', 'Time', 'ftim', [
        ('VII',  '+45s timer', 0, 2.0, {'type': 'time', 'value': 45}),
        ('VIII', '+60s timer (mega maintenance)', 1, 2.4, {'type': 'time', 'value': 60}),
    ], base_cost=14, base_tier=6)

    # ====== PHASED MECHANIC NODES — one per phase of the run ======
    # Click Echo: ghost click on each player click. Useful in click-heavy early phase.
    # Tier 3 → ×2 cost multiplier → 30 DP (cheap, early-game milestone)
    nodes.append({
        'id': 'mech_echo', 'name': 'Click Echo', 'desc': 'Each click has 25% chance to fire a ghost click at 60% power.',
        'branch': 'manual', 'tier': 3, 'cost': int(15 * TIER_COST_MULT[3]),  # 30
        'effect': {'type': 'click_echo', 'value': 0.25},
        'prereqs': [],
    })
    counter[0] += 1
    # Compound Bots: synergy across auto-click nodes — multiplier on total auto-CPS.
    # Tier 5 → ×5 → 350 DP (mid-game keystone — expensive when it unlocks)
    nodes.append({
        'id': 'mech_compbots', 'name': 'Compound Bots',
        'desc': 'Total auto-CPS multiplied by 1 + 4% × (auto-click nodes owned).',
        'branch': 'click', 'tier': 5, 'cost': int(70 * TIER_COST_MULT[5]),  # 350
        'effect': {'type': 'compound_bots'},
        'prereqs': [],
    })
    counter[0] += 1
    # Background Sweep: late-game idle dominator — A treats idle time as if at R cap.
    # Tier 7 → ×50 → 7500 DP (significant late-game purchase)
    nodes.append({
        'id': 'mech_bgsweep', 'name': 'Background Sweep',
        'desc': 'When idle 5+s, Auto Speed multiplied by (R cap / base R).',
        'branch': 'auto', 'tier': 7, 'cost': int(150 * TIER_COST_MULT[7]),  # 7500
        'effect': {'type': 'background_sweep'},
        'prereqs': [],
    })
    counter[0] += 1

    # Cross-prereq capstones for organic branching
    by_id = {n['id']: n for n in nodes}

    def add_cross(target_id, extras):
        if target_id and target_id in by_id:
            for e in extras:
                if e and e in by_id and e not in by_id[target_id]['prereqs']:
                    by_id[target_id]['prereqs'].append(e)

    if rhythm_ids:    add_cross(rhythm_ids[-1], [power_ids[-1], rate_ids[-1]])
    if idle_ids:      add_cross(idle_ids[-1],   [thru_ids[-1], resist_ids[-1]])
    if hybrid_ids:    add_cross(hybrid_ids[-1], [power_ids[-1], thru_ids[-1], time_ids[-1]])
    if cond_ids:      add_cross(cond_ids[-1],   [badsec_ids[-1], alloc_ids[-1]])
    if focus_ids:     add_cross(focus_ids[-1],  [power_ids[-1]])
    if finish_ids:    add_cross(finish_ids[-1], [thru_ids[-1]])
    if shatres_ids:   add_cross(shatres_ids[-1],[alloc_ids[-1]])
    if crit_ids:      add_cross(crit_ids[-1],   [rate_ids[-1], power_ids[-1]])

    return nodes


SKILL_NODES = build_skill_nodes()
SKILL_BY_ID = {n['id']: n for n in SKILL_NODES}

# ============================================================================
# LEGACY (PRESTIGE) TREE - multiplicative scaling
# ============================================================================

LEGACY_NODES = [
    # ============ EXISTING TREE (+25% costs) ============
    # Manual — Grip Training I-IV (existing) + V-VII (new numerical extensions)
    {'id': 'lm_grip1', 'name': 'Grip Training I',   'desc': 'Manual Power x1.15 (compounding)', 'branch': 'manual', 'cost': 1,  'effect': {'type': 'M_mult', 'value': 1.15}, 'prereqs': []},
    {'id': 'lm_grip2', 'name': 'Grip Training II',  'desc': 'Manual Power x1.20',               'branch': 'manual', 'cost': 3,  'effect': {'type': 'M_mult', 'value': 1.20}, 'prereqs': ['lm_grip1']},
    {'id': 'lm_grip3', 'name': 'Grip Training III', 'desc': 'Manual Power x1.30',               'branch': 'manual', 'cost': 5,  'effect': {'type': 'M_mult', 'value': 1.30}, 'prereqs': ['lm_grip2']},
    {'id': 'lm_grip4', 'name': 'Grip Training IV',  'desc': 'Manual Power x1.50',               'branch': 'manual', 'cost': 9,  'effect': {'type': 'M_mult', 'value': 1.50}, 'prereqs': ['lm_grip3']},
    {'id': 'lm_grip5', 'name': 'Grip Training V',   'desc': 'Manual Power x1.60',               'branch': 'manual', 'cost': 11, 'effect': {'type': 'M_mult', 'value': 1.60}, 'prereqs': ['lm_grip4']},
    {'id': 'lm_grip6', 'name': 'Grip Training VI',  'desc': 'Manual Power x1.70',               'branch': 'manual', 'cost': 16, 'effect': {'type': 'M_mult', 'value': 1.70}, 'prereqs': ['lm_grip5']},
    {'id': 'lm_grip7', 'name': 'Grip Training VII', 'desc': 'Manual Power x1.80',               'branch': 'manual', 'cost': 22, 'effect': {'type': 'M_mult', 'value': 1.80}, 'prereqs': ['lm_grip6']},
    # Carryover (manual branch mechanic perk)
    {'id': 'lp_carryover', 'name': 'DP Carryover',   'desc': 'Keep 20% of DP across prestige (instead of full reset)', 'branch': 'manual', 'cost': 8, 'effect': {'type': 'dp_carryover_pct', 'value': 0.20}, 'prereqs': []},

    # Click — Quick Reflexes I-III (existing) + IV-V (new) + Resident Bot (existing) + Lucky Click (perk)
    {'id': 'lc_reflex1', 'name': 'Quick Reflexes I',   'desc': 'CPS Cap x1.15',                         'branch': 'click', 'cost': 1,  'effect': {'type': 'R_mult', 'value': 1.15}, 'prereqs': []},
    {'id': 'lc_reflex2', 'name': 'Quick Reflexes II',  'desc': 'CPS Cap x1.20',                         'branch': 'click', 'cost': 3,  'effect': {'type': 'R_mult', 'value': 1.20}, 'prereqs': ['lc_reflex1']},
    {'id': 'lc_reflex3', 'name': 'Quick Reflexes III', 'desc': 'CPS Cap x1.30',                         'branch': 'click', 'cost': 5,  'effect': {'type': 'R_mult', 'value': 1.30}, 'prereqs': ['lc_reflex2']},
    {'id': 'lc_reflex4', 'name': 'Quick Reflexes IV',  'desc': 'CPS Cap x1.40',                         'branch': 'click', 'cost': 7,  'effect': {'type': 'R_mult', 'value': 1.40}, 'prereqs': ['lc_reflex3']},
    {'id': 'lc_reflex5', 'name': 'Quick Reflexes V',   'desc': 'CPS Cap x1.50',                         'branch': 'click', 'cost': 12, 'effect': {'type': 'R_mult', 'value': 1.50}, 'prereqs': ['lc_reflex4']},
    {'id': 'lc_auto1',   'name': 'Resident Bot I',     'desc': '+0.5 base auto-clicks/sec',             'branch': 'click', 'cost': 3,  'effect': {'type': 'auto_click_base', 'value': 0.5}, 'prereqs': []},
    {'id': 'lc_auto2',   'name': 'Resident Bot II',    'desc': '+1.5 base auto-clicks/sec',             'branch': 'click', 'cost': 5,  'effect': {'type': 'auto_click_base', 'value': 1.5}, 'prereqs': ['lc_auto1']},
    {'id': 'lp_lucky',   'name': 'Lucky Click',        'desc': '+5% baseline crit chance (stacks on top of skill nodes)', 'branch': 'click', 'cost': 4, 'effect': {'type': 'crit_baseline', 'value': 0.05}, 'prereqs': []},

    # Auto — Persistent Service I-III (existing) + IV-V (new) + Quiet Running I-II (existing) + III (new)
    {'id': 'la_serv1',  'name': 'Persistent Service I',   'desc': 'Auto Speed x1.20',  'branch': 'auto', 'cost': 1,  'effect': {'type': 'A_mult', 'value': 1.20}, 'prereqs': []},
    {'id': 'la_serv2',  'name': 'Persistent Service II',  'desc': 'Auto Speed x1.30',  'branch': 'auto', 'cost': 3,  'effect': {'type': 'A_mult', 'value': 1.30}, 'prereqs': ['la_serv1']},
    {'id': 'la_serv3',  'name': 'Persistent Service III', 'desc': 'Auto Speed x1.50',  'branch': 'auto', 'cost': 5,  'effect': {'type': 'A_mult', 'value': 1.50}, 'prereqs': ['la_serv2']},
    {'id': 'la_serv4',  'name': 'Persistent Service IV',  'desc': 'Auto Speed x1.60',  'branch': 'auto', 'cost': 7,  'effect': {'type': 'A_mult', 'value': 1.60}, 'prereqs': ['la_serv3']},
    {'id': 'la_serv5',  'name': 'Persistent Service V',   'desc': 'Auto Speed x1.75',  'branch': 'auto', 'cost': 12, 'effect': {'type': 'A_mult', 'value': 1.75}, 'prereqs': ['la_serv4']},
    {'id': 'la_quiet1', 'name': 'Quiet Running I',        'desc': 'Efficiency x1.08',  'branch': 'auto', 'cost': 3,  'effect': {'type': 'E_mult', 'value': 1.08}, 'prereqs': []},
    {'id': 'la_quiet2', 'name': 'Quiet Running II',       'desc': 'Efficiency x1.10',  'branch': 'auto', 'cost': 5,  'effect': {'type': 'E_mult', 'value': 1.10}, 'prereqs': ['la_quiet1']},
    {'id': 'la_quiet3', 'name': 'Quiet Running III',      'desc': 'Efficiency x1.12',  'branch': 'auto', 'cost': 7,  'effect': {'type': 'E_mult', 'value': 1.12}, 'prereqs': ['la_quiet2']},

    # Time — Longer Windows + Time Capsule (mechanic)
    {'id': 'lt_shift1',  'name': 'Longer Windows I',   'desc': '+30s base session timer',  'branch': 'time', 'cost': 3,  'effect': {'type': 'timer', 'value': 30},  'prereqs': []},
    {'id': 'lt_shift2',  'name': 'Longer Windows II',  'desc': '+60s base session timer',  'branch': 'time', 'cost': 5,  'effect': {'type': 'timer', 'value': 60},  'prereqs': ['lt_shift1']},
    {'id': 'lt_shift3',  'name': 'Longer Windows III', 'desc': '+120s base session timer', 'branch': 'time', 'cost': 9,  'effect': {'type': 'timer', 'value': 120}, 'prereqs': ['lt_shift2']},
    {'id': 'lp_timecap1','name': 'Time Capsule I',     'desc': '+15s base timer (additional, all disks)',  'branch': 'time', 'cost': 5,  'effect': {'type': 'timer', 'value': 15}, 'prereqs': []},
    {'id': 'lp_timecap2','name': 'Time Capsule II',    'desc': '+30s base timer (additional)',             'branch': 'time', 'cost': 10, 'effect': {'type': 'timer', 'value': 30}, 'prereqs': ['lp_timecap1']},

    # Knowledge — historians + start_frag + Insulator (mechanic) + Inherit Stacks (mechanic)
    {'id': 'lk_hist1',    'name': 'Drive Historian',      'desc': 'Frag Resistance +0.10',                       'branch': 'knowledge', 'cost': 3, 'effect': {'type': 'FR_add', 'value': 0.10}, 'prereqs': []},
    {'id': 'lk_hist2',    'name': 'Drive Archaeologist',  'desc': 'Frag Resistance +0.15',                       'branch': 'knowledge', 'cost': 5, 'effect': {'type': 'FR_add', 'value': 0.15}, 'prereqs': ['lk_hist1']},
    {'id': 'lk_start1',   'name': 'Pre-flight Check',     'desc': 'Start every disk with 15% less initial frag', 'branch': 'knowledge', 'cost': 4, 'effect': {'type': 'start_frag_reduce', 'value': 0.15}, 'prereqs': []},
    {'id': 'lk_start2',   'name': 'Master Diagnostician', 'desc': 'Start every disk with 30% less initial frag', 'branch': 'knowledge', 'cost': 8, 'effect': {'type': 'start_frag_reduce', 'value': 0.30}, 'prereqs': ['lk_start1']},
    {'id': 'lp_insul1',   'name': 'Insulator I',          'desc': 'Write intensity x0.90 (less re-frag)',        'branch': 'knowledge', 'cost': 5,  'effect': {'type': 'write_intensity_mult', 'value': 0.90}, 'prereqs': []},
    {'id': 'lp_insul2',   'name': 'Insulator II',         'desc': 'Write intensity x0.80 (additional)',          'branch': 'knowledge', 'cost': 10, 'effect': {'type': 'write_intensity_mult', 'value': 0.80}, 'prereqs': ['lp_insul1']},
    {'id': 'lp_inherit1', 'name': 'Inherit Stacks I',     'desc': 'Keep 25% of repeatable stacks across prestige', 'branch': 'knowledge', 'cost': 6,  'effect': {'type': 'inherit_stacks_pct', 'value': 0.25}, 'prereqs': []},
    {'id': 'lp_inherit2', 'name': 'Inherit Stacks II',    'desc': 'Keep 50% of repeatable stacks across prestige', 'branch': 'knowledge', 'cost': 12, 'effect': {'type': 'inherit_stacks_pct', 'value': 0.50}, 'prereqs': ['lp_inherit1']},

    # Scaling — DP/LP multipliers (existing) + Quick Start + Veteran (mechanic) + 5 milestone-gated unlocks
    {'id': 'ls_dp1',          'name': 'Defrag Payout I',     'desc': 'DP earned x1.25',                                                                         'branch': 'scaling', 'cost': 3,  'effect': {'type': 'dp_mult', 'value': 1.25}, 'prereqs': []},
    {'id': 'ls_dp2',          'name': 'Defrag Payout II',    'desc': 'DP earned x1.50',                                                                         'branch': 'scaling', 'cost': 5,  'effect': {'type': 'dp_mult', 'value': 1.50}, 'prereqs': ['ls_dp1']},
    {'id': 'ls_dp3',          'name': 'Defrag Payout III',   'desc': 'DP earned x2.00',                                                                         'branch': 'scaling', 'cost': 9,  'effect': {'type': 'dp_mult', 'value': 2.00}, 'prereqs': ['ls_dp2']},
    {'id': 'ls_lp1',          'name': 'Legacy Payout I',     'desc': 'LP earned x1.50',                                                                         'branch': 'scaling', 'cost': 5,  'effect': {'type': 'lp_mult', 'value': 1.50}, 'prereqs': ['ls_dp2']},
    {'id': 'ls_lp2',          'name': 'Legacy Payout II',    'desc': 'LP earned x2.00',                                                                         'branch': 'scaling', 'cost': 10, 'effect': {'type': 'lp_mult', 'value': 2.00}, 'prereqs': ['ls_lp1']},
    {'id': 'lp_quickstart',   'name': 'Quick Start',         'desc': 'For the first 5 sessions after each prestige, auto-buy cheapest affordable on disk start','branch': 'scaling', 'cost': 4,  'effect': {'type': 'quick_start_sessions', 'value': 5},   'prereqs': []},
    {'id': 'lp_veteran',      'name': 'Veteran Operator',    'desc': '+5 starting DP per prestige cycle (multiplied by prestige_count)',                       'branch': 'scaling', 'cost': 6,  'effect': {'type': 'dp_per_prestige', 'value': 5},        'prereqs': []},
    # Milestone-gated nodes — require both LP and the listed prestige_count threshold to unlock
    {'id': 'lp_architect',    'name': 'Architect',           'desc': 'Future legacy purchases cost 10% less LP (requires Prestige #3)',                       'branch': 'scaling', 'cost': 12, 'effect': {'type': 'lp_cost_mult',  'value': 0.90}, 'min_prestige_count': 3,  'prereqs': []},
    {'id': 'lp_sage',         'name': 'Sage',                'desc': 'All skill tier requirements reduced by 1 (requires Prestige #5)',                       'branch': 'scaling', 'cost': 20, 'effect': {'type': 'tier_offset',    'value': 1},    'min_prestige_count': 5,  'prereqs': []},
    {'id': 'lp_master',       'name': 'Master',              'desc': 'C: and D: auto-complete on session start (requires Prestige #8)',                      'branch': 'scaling', 'cost': 25, 'effect': {'type': 'auto_clear_orders', 'value': 2}, 'min_prestige_count': 8,  'prereqs': []},
    {'id': 'lp_grandmaster',  'name': 'Grandmaster',         'desc': 'Each repeatable node starts each life with 2 free stacks (requires Prestige #12)',     'branch': 'scaling', 'cost': 35, 'effect': {'type': 'free_rep_stacks', 'value': 2}, 'min_prestige_count': 12, 'prereqs': []},
    {'id': 'lp_resetmastery', 'name': 'Reset Mastery',       'desc': '+5 LP awarded at every prestige (requires Prestige #15)',                              'branch': 'scaling', 'cost': 30, 'effect': {'type': 'starting_lp',     'value': 5}, 'min_prestige_count': 15, 'prereqs': []},
]

LEGACY_BY_ID = {n['id']: n for n in LEGACY_NODES}


# ============================================================================
# BOUNDED-REPEATABLE NODES (per-life, reset on prestige)
# ----------------------------------------------------------------------------
# Each can be bought up to `max_stacks` times. Cost grows geometrically per
# stack owned: cost(stacks) = int(base_cost * cost_growth ** stacks).
# Effects stack additively per copy.
# ============================================================================

REPEATABLE_NODES = [
    {
        'id': 'rep_power', 'name': 'Compounding Power', 'branch': 'manual', 'tier': 3,
        'desc': '+0.6% Manual Power per stack',
        'effect': {'type': 'M', 'value': 0.006},
        'base_cost': 18, 'cost_growth': 1.50, 'max_stacks': 25,
        'prereqs': [],
    },
    {
        'id': 'rep_botmult', 'name': 'Bot Stack Multiplier', 'branch': 'click', 'tier': 4,
        'desc': 'Total auto-click rate +4% per stack',
        'effect': {'type': 'autoclick_mult_add', 'value': 0.04},
        'base_cost': 32, 'cost_growth': 1.60, 'max_stacks': 22,
        'prereqs': [],
    },
    {
        'id': 'rep_heatsink', 'name': 'Compound Heatsink', 'branch': 'auto', 'tier': 3,
        'desc': '+0.8% Auto Speed per stack',
        'effect': {'type': 'A', 'value': 0.008},
        'base_cost': 20, 'cost_growth': 1.55, 'max_stacks': 28,
        'prereqs': [],
    },
    {
        'id': 'rep_alloc', 'name': 'Adaptive Allocator', 'branch': 'fs', 'tier': 5,
        'desc': 'All file-type costs −0.3% per stack',
        'effect': {'type': 'file_cost_all', 'value': 0.003},
        'base_cost': 45, 'cost_growth': 1.65, 'max_stacks': 20,
        'prereqs': [],
    },
]
REPEATABLE_BY_ID = {n['id']: n for n in REPEATABLE_NODES}


def repeatable_cost(node, stacks_owned: int) -> int:
    """Stack-priced + scales with disk progress. Late-game stacks are genuinely expensive
    because base_cost gets multiplied by (1 + 0.5 × highest_cleared_order)."""
    disk_mult = 1.0 + 0.5 * get_highest_cleared_order()
    return int(node['base_cost'] * disk_mult * (node['cost_growth'] ** stacks_owned))


def can_purchase_repeatable(node, stacks_owned: int, dp: int, unlocked_tier: int) -> bool:
    if stacks_owned >= node['max_stacks']:
        return False
    # Sage tier offset also applies to repeatable nodes
    effective_req = max(1, node.get('tier', 99) - gs.legacy_tier_offset)
    if effective_req > unlocked_tier:
        return False
    if dp < repeatable_cost(node, stacks_owned):
        return False
    return True


def effective_legacy_cost(node) -> int:
    """Apply Architect discount to a legacy node's LP cost."""
    return max(1, int(node['cost'] * gs.legacy_lp_cost_mult))


def validate_skill_tree():
    """Ensure all prereqs resolve to actual node IDs (catches generator bugs)."""
    ids = set(SKILL_BY_ID)
    for n in SKILL_NODES:
        for p in n['prereqs']:
            assert p in ids, f"Skill prereq {p} on {n['id']} missing"
    lids = set(LEGACY_BY_ID)
    for n in LEGACY_NODES:
        for p in n.get('prereqs', []):
            assert p in lids, f"Legacy prereq {p} on {n['id']} missing"


validate_skill_tree()

# ============================================================================
# CELL + GAMESTATE
# ============================================================================

@dataclass
class Cell:
    state: str       # "good" | "fragmented"
    file_type: str   # "temp" | "doc" | "media" | "sys"


# Persistent fields are serialized. Transient fields are recomputed per session.
PERSISTENT_FIELDS = (
    'highest_disk_cleared', 'purchased_legacy', 'total_lifetime_cleaned',
    'prestige_count', 'prestige_lifetime_baseline',
    'purchased_nodes', 'purchased_repeatable', 'current_dp', 'unspent_lp', 'extra_timer_secs',
    'current_disk', 'shatter_count_lifetime', 'sessions_since_prestige',
)


@dataclass
class GameState:
    # Persistent across save/load
    highest_disk_cleared: str | None = None
    purchased_legacy: set[str] = field(default_factory=set)
    total_lifetime_cleaned: int = 0
    prestige_count: int = 0
    prestige_lifetime_baseline: int = 0
    shatter_count_lifetime: int = 0

    purchased_nodes: set[str] = field(default_factory=set)
    # Bounded-repeatable nodes: id -> stack count (per-life, reset on prestige)
    purchased_repeatable: dict = field(default_factory=dict)
    current_dp: int = 0
    unspent_lp: int = 0
    extra_timer_secs: float = 0.0
    current_disk: str = 'C:'

    # Transient — recomputed on demand
    grid: list[list[Cell]] = field(default_factory=list)
    fragmented_count: int = 0
    fragmentation: float = 0.0
    # (r, c) -> wall-clock expire-time for the transient highlight border when a cell
    # changes state (cleaned / shattered into / refragged). Drawn in draw_defrag_grid.
    # Replaces the older sweep-particle animation system.
    cell_highlights: dict = field(default_factory=dict)
    time_left: float = 0.0
    re_frag_accum: float = 0.0
    session_cleaned: int = 0
    session_shatter_events: int = 0
    session_end_reason: str = ''
    earned_dp: int = 0
    earned_lp: int = 0
    victory_celebration_until: float = 0.0
    prestige_banner_until: float = 0.0

    # Click rate
    click_timestamps: deque = field(default_factory=lambda: deque(maxlen=400))
    auto_click_accum: float = 0.0
    rate_capped_recent: float = 0.0  # for "Rate Capped!" feedback

    # Computed stats
    current_M: float = BASE_M
    current_R: float = BASE_R
    current_A: float = BASE_A
    current_E: float = BASE_E
    current_FR: float = BASE_FR
    current_autoclick: float = BASE_AUTOCLICK
    current_crit_chance: float = 0.0
    current_click_multi: float = 1.0
    current_M_high: float = 0.0   # additional M when frag>55%
    current_M_low: float = 0.0    # additional M when frag<25%
    current_A_idle: float = 0.0
    current_A_low: float = 0.0
    current_type_costs: dict = field(default_factory=lambda: dict(BASE_TYPE_COSTS))
    current_vs_power_mult: dict = field(default_factory=lambda: {k: 1.0 for k in BASE_TYPE_COSTS})
    current_shatter_resist: float = 0.0
    current_shatter_dp: float = 0.0
    current_dp_mult: float = 1.0
    current_lp_mult: float = 1.0
    current_start_frag_reduce: float = 0.0
    # Phased mechanic flags
    current_click_echo_chance: float = 0.0
    current_background_sweep_active: bool = False
    # Quick Start state — counts sessions started since last prestige
    sessions_since_prestige: int = 999

    # Legacy raw bonuses
    legacy_M_mult: float = 1.0
    legacy_R_mult: float = 1.0
    legacy_A_mult: float = 1.0
    legacy_E_mult: float = 1.0
    legacy_FR_add: float = 0.0
    legacy_timer_add: float = 0.0
    legacy_autoclick_base: float = 0.0
    legacy_dp_mult: float = 1.0
    legacy_lp_mult: float = 1.0
    legacy_start_frag_reduce: float = 0.0
    # New legacy effects from mechanic perks + milestones
    legacy_crit_baseline: float = 0.0           # Lucky Click adds to baseline crit chance
    legacy_write_intensity_mult: float = 1.0    # Insulator I/II (multiplicative each)
    legacy_dp_carryover_pct: float = 0.0        # DP Carryover — % of DP kept across prestige
    legacy_inherit_stacks_pct: float = 0.0      # Inherit Stacks — % of repeatables kept
    legacy_quick_start_sessions: int = 0        # Quick Start — number of post-prestige sessions to auto-buy
    legacy_dp_per_prestige: int = 0             # Veteran Operator — starting DP bonus per prestige_count
    legacy_lp_cost_mult: float = 1.0            # Architect — discount on future legacy LP costs
    legacy_tier_offset: int = 0                 # Sage — reduces tier requirement
    legacy_auto_clear_orders: int = 0           # Master — auto-clear disks with order <= this
    legacy_free_rep_stacks: int = 0             # Grandmaster — free starting stacks per repeatable
    legacy_starting_lp: int = 0                 # Reset Mastery — bonus LP on every prestige

    def to_persistent_dict(self) -> dict:
        out = {}
        for f in PERSISTENT_FIELDS:
            v = getattr(self, f)
            if isinstance(v, set):
                v = sorted(v)
            out[f] = v
        return out

    @classmethod
    def from_persistent_dict(cls, d: dict) -> 'GameState':
        gs = cls()
        for f in PERSISTENT_FIELDS:
            if f in d:
                v = d[f]
                if f in ('purchased_legacy', 'purchased_nodes'):
                    v = set(v)
                setattr(gs, f, v)
        # Drop any owned IDs that don't exist in the current node set
        gs.purchased_nodes &= set(SKILL_BY_ID)
        gs.purchased_legacy &= set(LEGACY_BY_ID)
        # Same for repeatables (drop unknown keys)
        gs.purchased_repeatable = {k: int(v) for k, v in gs.purchased_repeatable.items()
                                   if k in REPEATABLE_BY_ID}
        return gs


gs = GameState()


# ============================================================================
# SAVE / LOAD
# ============================================================================

def save_dir() -> Path:
    # Pick the right per-OS app-data location. On Linux this is the existing
    # XDG path, so saves made by earlier builds keep loading.
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA') or Path.home())
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME') or (Path.home() / '.local' / 'share'))
    p = base / 'defrag.exe' / 'saves'
    p.mkdir(parents=True, exist_ok=True)
    return p


def slot_path(slot: int) -> Path:
    return save_dir() / f'slot{slot}.json'


def save_game(slot: int) -> bool:
    try:
        path = slot_path(slot)
        path.write_text(json.dumps(gs.to_persistent_dict(), indent=2))
        return True
    except (OSError, TypeError, ValueError):
        return False


def load_game(slot: int) -> bool:
    global gs
    try:
        path = slot_path(slot)
        if not path.exists():
            return False
        data = json.loads(path.read_text())
        gs = GameState.from_persistent_dict(data)
        recompute_legacy_bonuses()
        recompute_stats()
        return True
    except (OSError, json.JSONDecodeError, ValueError):
        return False


def slot_summary(slot: int) -> dict | None:
    """Lightweight peek for the slot list — returns None if no save."""
    try:
        path = slot_path(slot)
        if not path.exists():
            return None
        d = json.loads(path.read_text())
        return {
            'highest': d.get('highest_disk_cleared') or '—',
            'prestige': d.get('prestige_count', 0),
            'cleaned': d.get('total_lifetime_cleaned', 0),
        }
    except (OSError, json.JSONDecodeError):
        return None


def delete_slot(slot: int) -> bool:
    try:
        p = slot_path(slot)
        if p.exists():
            p.unlink()
        return True
    except OSError:
        return False


# ============================================================================
# CORE SIM
# ============================================================================

def has_auto_progress_unlock() -> bool:
    """True iff any Auto-branch skill node is owned."""
    for nid in gs.purchased_nodes:
        node = SKILL_BY_ID.get(nid)
        if node and node['branch'] == 'auto':
            return True
    return False


def can_purchase(node, purchased_set, dp, unlocked_tier) -> bool:
    if node['id'] in purchased_set:
        return False
    # Sage legacy reduces the effective tier requirement by legacy_tier_offset
    effective_req = max(1, node.get('tier', 99) - gs.legacy_tier_offset)
    if effective_req > unlocked_tier:
        return False
    if not all(p in purchased_set for p in node.get('prereqs', [])):
        return False
    if dp < node.get('cost', 999):
        return False
    return True


def get_highest_cleared_order() -> int:
    if not gs.highest_disk_cleared:
        return 0
    return DISK_ORDER.get(gs.highest_disk_cleared, 0)


def get_unlocked_tier() -> int:
    """Skill tier cap. A new tier roughly every 2-3 disks. Tier 10 caps at clearing U:.
    Some legacy data (Botnet, AI Clicker, Bot Farm) has tiers up to 10, so we extend the
    progression there. Past tier 10 the player grinds repeatables to Z:.
    Thresholds list is checked highest-first."""
    o = get_highest_cleared_order()
    for need, tier in [(20, 10), (17, 9), (15, 8), (12, 7), (9, 6), (6, 5), (4, 4), (3, 3), (1, 2)]:
        if o >= need:
            return tier
    return 1


def get_disk_timer(disk_key: str) -> float:
    return DISKS[disk_key]['base_timer'] + gs.extra_timer_secs + gs.legacy_timer_add


def recompute_legacy_bonuses():
    gs.legacy_M_mult = 1.0
    gs.legacy_R_mult = 1.0
    gs.legacy_A_mult = 1.0
    gs.legacy_E_mult = 1.0
    gs.legacy_FR_add = 0.0
    gs.legacy_timer_add = 0.0
    gs.legacy_autoclick_base = 0.0
    gs.legacy_dp_mult = 1.0
    gs.legacy_lp_mult = 1.0
    gs.legacy_start_frag_reduce = 0.0
    # New legacy effects
    gs.legacy_crit_baseline = 0.0
    gs.legacy_write_intensity_mult = 1.0
    gs.legacy_dp_carryover_pct = 0.0
    gs.legacy_inherit_stacks_pct = 0.0
    gs.legacy_quick_start_sessions = 0
    gs.legacy_dp_per_prestige = 0
    gs.legacy_lp_cost_mult = 1.0
    gs.legacy_tier_offset = 0
    gs.legacy_auto_clear_orders = 0
    gs.legacy_free_rep_stacks = 0
    gs.legacy_starting_lp = 0
    for lid in gs.purchased_legacy:
        node = LEGACY_BY_ID.get(lid)
        if not node:
            continue
        eff = node['effect']
        t = eff['type']
        v = eff['value']
        if   t == 'M_mult':                gs.legacy_M_mult *= v
        elif t == 'R_mult':                gs.legacy_R_mult *= v
        elif t == 'A_mult':                gs.legacy_A_mult *= v
        elif t == 'E_mult':                gs.legacy_E_mult *= v
        elif t == 'FR_add':                gs.legacy_FR_add += v
        elif t == 'timer':                 gs.legacy_timer_add += v
        elif t == 'auto_click_base':       gs.legacy_autoclick_base += v
        elif t == 'dp_mult':               gs.legacy_dp_mult *= v
        elif t == 'lp_mult':               gs.legacy_lp_mult *= v
        elif t == 'start_frag_reduce':     gs.legacy_start_frag_reduce += v
        # New effect types
        elif t == 'crit_baseline':         gs.legacy_crit_baseline += v
        elif t == 'write_intensity_mult':  gs.legacy_write_intensity_mult *= v
        elif t == 'dp_carryover_pct':      gs.legacy_dp_carryover_pct = max(gs.legacy_dp_carryover_pct, v)
        elif t == 'inherit_stacks_pct':    gs.legacy_inherit_stacks_pct = max(gs.legacy_inherit_stacks_pct, v)
        elif t == 'quick_start_sessions':  gs.legacy_quick_start_sessions = max(gs.legacy_quick_start_sessions, int(v))
        elif t == 'dp_per_prestige':       gs.legacy_dp_per_prestige += int(v)
        elif t == 'lp_cost_mult':          gs.legacy_lp_cost_mult *= v
        elif t == 'tier_offset':           gs.legacy_tier_offset += int(v)
        elif t == 'auto_clear_orders':     gs.legacy_auto_clear_orders = max(gs.legacy_auto_clear_orders, int(v))
        elif t == 'free_rep_stacks':       gs.legacy_free_rep_stacks = max(gs.legacy_free_rep_stacks, int(v))
        elif t == 'starting_lp':           gs.legacy_starting_lp += int(v)


def prestige_global_mult() -> float:
    """Each prestige adds +100% to M/A/E (in addition to legacies). Sim-tuned for
    1-2h target playthrough — at this rate ~5-10 prestige cycles reach Z:."""
    return 1.0 + 1.00 * gs.prestige_count


def recompute_stats():
    """Recompute all current_* from BASE + legacy + per-life nodes + repeatables + mechanics."""
    g = prestige_global_mult()

    m_add = 0.0; r_add = 0.0; a_add = 0.0; e_add = 0.0; fr_add = 0.0
    m_hi  = 0.0; m_lo = 0.0; a_low = 0.0; a_idle = 0.0
    autoclick = 0.0
    autoclick_mult = 1.0   # multiplied by Bot Stack Multiplier stacks + Compound Bots mechanic
    crit = 0.0; click_multi = 1.0
    shatter_resist = 0.0; shatter_dp = 0.0
    type_costs = dict(BASE_TYPE_COSTS)
    vs_power = {k: 1.0 for k in BASE_TYPE_COSTS}
    # Mechanic flags
    click_echo_chance = 0.0
    background_sweep_owned = False
    compound_bots_owned = False
    n_autoclick_nodes = 0  # for Compound Bots synergy

    for nid in gs.purchased_nodes:
        node = SKILL_BY_ID.get(nid)
        if not node:
            continue
        eff = node['effect']
        t = eff['type']
        if   t == 'M':           m_add += eff['value']
        elif t == 'R':           r_add += eff['value']
        elif t == 'A':           a_add += eff['value']
        elif t == 'E':           e_add += eff['value']
        elif t == 'FR':          fr_add += eff['value']
        elif t == 'M_high':      m_hi  += eff['value']
        elif t == 'M_low':       m_lo  += eff['value']
        elif t == 'A_low':       a_low += eff['value']
        elif t == 'A_idle':      a_idle += eff['value']
        elif t == 'auto_click':
            autoclick += eff['value']
            n_autoclick_nodes += 1
        elif t == 'crit_chance': crit += eff['value']
        elif t == 'click_multi': click_multi += eff['value']
        elif t == 'shatter_resist': shatter_resist += eff['value']
        elif t == 'shatter_dp':  shatter_dp += eff['value']
        elif t == 'file_cost':
            type_costs[eff['target']] *= (1.0 - eff['reduce'])
        elif t == 'file_power':
            vs_power[eff['target']] *= eff['mult']
        elif t == 'click_echo':
            click_echo_chance = max(click_echo_chance, eff['value'])
        elif t == 'compound_bots':
            compound_bots_owned = True
        elif t == 'background_sweep':
            background_sweep_owned = True
        # 'time' handled separately when buying

    # Bounded-repeatable nodes — apply stack-count * per-stack effect
    for rid, stacks in gs.purchased_repeatable.items():
        node = REPEATABLE_BY_ID.get(rid)
        if not node or stacks <= 0:
            continue
        eff = node['effect']
        t = eff['type']
        v = eff['value']
        if   t == 'M':                  m_add += v * stacks
        elif t == 'A':                  a_add += v * stacks
        elif t == 'autoclick_mult_add': autoclick_mult += v * stacks
        elif t == 'file_cost_all':
            for k in type_costs:
                type_costs[k] *= (1.0 - v) ** stacks

    # Apply base + per-life additive + legacy multiplicative + prestige global
    gs.current_M  = BASE_M  * (1.0 + m_add) * gs.legacy_M_mult * g
    gs.current_R  = (BASE_R + r_add) * gs.legacy_R_mult * (1.0 + 0.05 * (g - 1.0))
    gs.current_A  = BASE_A  * (1.0 + a_add) * gs.legacy_A_mult * g
    gs.current_E  = BASE_E  * (1.0 + e_add) * gs.legacy_E_mult
    gs.current_FR = min(0.90, BASE_FR + fr_add + gs.legacy_FR_add)

    # Auto must be unlocked by buying any Auto-branch node first; if none, A floors at 0
    if not has_auto_progress_unlock():
        gs.current_A = 0.0

    # Apply Compound Bots synergy if owned: total auto-CPS multiplied by 1 + 0.04 × n_autoclick_nodes
    if compound_bots_owned:
        autoclick_mult += 0.04 * n_autoclick_nodes

    gs.current_autoclick = (autoclick + gs.legacy_autoclick_base) * autoclick_mult
    gs.current_crit_chance = min(0.5, crit + gs.legacy_crit_baseline)
    gs.current_click_multi = click_multi
    gs.current_M_high = m_hi
    gs.current_M_low = m_lo
    gs.current_A_idle = a_idle
    gs.current_A_low = a_low
    gs.current_shatter_resist = min(0.85, shatter_resist)
    gs.current_shatter_dp = shatter_dp
    gs.current_type_costs = {k: max(0.15, v) for k, v in type_costs.items()}
    gs.current_vs_power_mult = vs_power
    gs.current_dp_mult = gs.legacy_dp_mult
    gs.current_lp_mult = gs.legacy_lp_mult
    gs.current_start_frag_reduce = gs.legacy_start_frag_reduce
    # Phased mechanics
    gs.current_click_echo_chance = click_echo_chance
    gs.current_background_sweep_active = background_sweep_owned


HIGHLIGHT_DURATION = 0.35  # seconds — how long the white outline lingers after a cell changes state


def _mark_cell_changed(r: int, c: int):
    """Tag a cell as 'just changed' so draw_defrag_grid will render a 1px white outline
    around it for HIGHLIGHT_DURATION seconds. Used for the visual feedback of click
    cleans, shatter spawns, and write re-frags."""
    gs.cell_highlights[(r, c)] = pygame.time.get_ticks() / 1000.0 + HIGHLIGHT_DURATION


def init_grid_for_disk(disk_key: str):
    disk = DISKS[disk_key]
    mix = disk['file_mix']
    types = list(mix.keys())
    weights = list(mix.values())
    start_frag = disk['start_frag'] * (1.0 - gs.current_start_frag_reduce)

    gs.grid = []
    for _r in range(GRID_ROWS):
        row = []
        for _c in range(GRID_COLS):
            ftype = random.choices(types, weights=weights, k=1)[0]
            is_frag = random.random() < start_frag
            row.append(Cell('fragmented' if is_frag else 'good', ftype))
        gs.grid.append(row)

    gs.cell_highlights = {}
    gs.re_frag_accum = 0.0
    gs.session_cleaned = 0
    gs.session_shatter_events = 0
    gs.click_timestamps.clear()
    gs.auto_click_accum = 0.0
    update_fragmentation()


def update_fragmentation():
    cnt = sum(1 for row in gs.grid for cell in row if cell.state == 'fragmented')
    gs.fragmented_count = cnt
    gs.fragmentation = (cnt / TOTAL_CELLS) * 100.0 if TOTAL_CELLS > 0 else 0.0


def _spawn_shatter(file_type: str, disk: dict, depth: int = 0):
    """When a fragment of `file_type` is cleaned, possibly spawn children of lower tier at random good cells."""
    children = list(disk.get('shatter', {}).get(file_type, []))
    if not children:
        return
    # Containment node reduces children count probabilistically
    resist = gs.current_shatter_resist
    if resist > 0:
        children = [c for c in children if random.random() > resist]
    cascade = disk.get('cascade_chance', 0.0)
    for child_type in children:
        # Find a random good cell to convert
        good = [(r, c) for r in range(GRID_ROWS) for c in range(GRID_COLS) if gs.grid[r][c].state == 'good']
        if not good:
            return
        r, c = random.choice(good)
        gs.grid[r][c].state = 'fragmented'
        gs.grid[r][c].file_type = child_type
        _mark_cell_changed(r, c)
        gs.session_shatter_events += 1
        gs.shatter_count_lifetime += 1
        # Cascade: re-shatter recursively (rare on early disks, common on late)
        if depth < 2 and random.random() < cascade:
            _spawn_shatter(child_type, disk, depth + 1)


def apply_power(budget: float) -> int:
    """Spend `budget` power on the cheapest fragments first; trigger shatter on cleaned.

    For cells of equal cost (same file type, same disk), the sort tie-breaks by (row, col)
    so the visible defrag sweep proceeds left-to-right within each row, top-to-bottom by row —
    the classic Win95 disk defragmenter sweep order."""
    if budget <= 0:
        return 0
    disk = DISKS[gs.current_disk]
    frags = []
    for r in range(GRID_ROWS):
        row = gs.grid[r]
        for c in range(GRID_COLS):
            cell = row[c]
            if cell.state == 'fragmented':
                raw = disk['hardness'] * gs.current_type_costs[cell.file_type]
                eff = raw / max(0.1, gs.current_vs_power_mult[cell.file_type])
                # Tuple order (eff, r, c, ftype) so ties break row-major
                frags.append((eff, r, c, cell.file_type))
    if not frags:
        return 0
    frags.sort()
    cleaned = 0
    for eff, r, c, ftype in frags:
        if budget < eff:
            break
        gs.grid[r][c].state = 'good'
        _mark_cell_changed(r, c)
        budget -= eff
        cleaned += 1
        gs.session_cleaned += 1
        gs.total_lifetime_cleaned += 1
        _spawn_shatter(ftype, disk)
    if cleaned > 0:
        update_fragmentation()
    return cleaned


def apply_refragmentation(dt: float):
    """Write traffic re-fragments cells. Disabled before first Auto unlock.
    Insulator legacy nodes multiplicatively reduce the disk's effective write_intensity."""
    if not has_auto_progress_unlock():
        return
    disk = DISKS[gs.current_disk]
    effective_write = disk['write_intensity'] * gs.legacy_write_intensity_mult
    rate = effective_write * max(0.0, 1.0 - gs.current_FR)
    gs.re_frag_accum += rate * dt
    types = list(disk['file_mix'].keys())
    weights = list(disk['file_mix'].values())
    while gs.re_frag_accum >= 1.0:
        good = [(r, c) for r in range(GRID_ROWS) for c in range(GRID_COLS) if gs.grid[r][c].state == 'good']
        if not good:
            gs.re_frag_accum = 0.0
            break
        r, c = random.choice(good)
        gs.grid[r][c].state = 'fragmented'
        gs.grid[r][c].file_type = random.choices(types, weights=weights, k=1)[0]
        _mark_cell_changed(r, c)
        gs.re_frag_accum -= 1.0
        update_fragmentation()


def _trim_click_window(now: float):
    while gs.click_timestamps and gs.click_timestamps[0] < now - CLICK_WINDOW:
        gs.click_timestamps.popleft()


def current_real_cps(now: float) -> float:
    _trim_click_window(now)
    return len(gs.click_timestamps) / CLICK_WINDOW


def trigger_manual_sweep(now: float):
    """Player click. Counts towards R cap; bursts immediate power if not capped.
    Click Echo mechanic: each accepted click has chance to fire a 'ghost' click at 60% power.
    The ghost does NOT count toward the R cap or the click_timestamps deque."""
    _trim_click_window(now)
    real_cps = len(gs.click_timestamps) / CLICK_WINDOW
    if real_cps >= gs.current_R:
        gs.rate_capped_recent = now
        return
    gs.click_timestamps.append(now)
    multiplier = gs.current_click_multi
    if random.random() < gs.current_crit_chance:
        multiplier *= 2.0
    burst = gs.current_M * gs.current_E * multiplier
    apply_power(burst)
    # Click Echo: extra ghost click at 60% power
    if gs.current_click_echo_chance > 0 and random.random() < gs.current_click_echo_chance:
        apply_power(burst * 0.60)
    # Click feedback is delivered by the cell-change highlight outlines that
    # apply_power and shatter set via _mark_cell_changed.


def update_continuous_progress(dt: float, now: float):
    """Per-frame sim tick: auto-clickers, conditional manual contrib, A passive."""
    # Auto-clicker virtual clicks contribute as if real clicks at M*E (no rate cap)
    gs.auto_click_accum += gs.current_autoclick * dt
    virtual_clicks = int(gs.auto_click_accum)
    if virtual_clicks > 0:
        gs.auto_click_accum -= virtual_clicks
        multi = gs.current_click_multi
        # batch crits via expectation to avoid per-click rolls when rate huge
        expected_crit_extra = gs.current_crit_chance * virtual_clicks
        eff_clicks = virtual_clicks + expected_crit_extra  # crit doubles → +1 per crit
        apply_power(gs.current_M * gs.current_E * multi * eff_clicks)

    # Continuous manual contribution from real CPS (above the burst already applied).
    frag_pct = gs.fragmentation
    a_eff = gs.current_A
    if a_eff > 0:
        # Time since last real click — used for both Idle bonus AND Background Sweep
        last_click = gs.click_timestamps[-1] if gs.click_timestamps else (now - 9999.0)
        idle_for = now - last_click
        real_active = current_real_cps(now) > 0.3
        if not real_active and gs.current_A_idle > 0:
            a_eff += gs.current_A * gs.current_A_idle
        if frag_pct < 25 and gs.current_A_low > 0:
            a_eff += gs.current_A * gs.current_A_low
        # Background Sweep mechanic — when idle 5+ seconds, A scales by R cap ratio.
        # This is the late-game power source that lets the player walk away.
        if gs.current_background_sweep_active and idle_for >= 5.0:
            a_eff *= max(1.0, gs.current_R / BASE_R)

    # M conditional adds to per-click effectiveness; apply as small continuous bonus
    # to make the "+M when high frag" nodes feel alive even if you click slowly
    m_cond_bonus = 0.0
    if frag_pct > 55:
        m_cond_bonus += gs.current_M * gs.current_M_high
    if frag_pct < 25:
        m_cond_bonus += gs.current_M * gs.current_M_low
    if m_cond_bonus > 0:
        # Approximate "bonus per second proportional to recent CPS"
        bonus_cps = current_real_cps(now) + gs.current_autoclick
        apply_power(m_cond_bonus * bonus_cps * gs.current_E * dt)

    if a_eff > 0:
        apply_power(a_eff * gs.current_E * dt)


# ============================================================================
# SESSIONS / PRESTIGE
# ============================================================================

# ----------------------------------------------------------------------------
# Pure-logic helpers (no pygame, no save_game, no UI state). The balance
# simulator drives these directly; the UI wrappers below call them and then
# add the IO/state-machine side effects.
# ----------------------------------------------------------------------------

def _quick_start_auto_buy():
    """Auto-buy cheapest affordable skill/repeatable in a loop (no UI). Used by Quick Start."""
    tier_cap = get_unlocked_tier()
    bought = 0
    while bought < 500:
        candidates = []
        for n in SKILL_NODES:
            if can_purchase(n, gs.purchased_nodes, gs.current_dp, tier_cap):
                candidates.append(('skill', n, n['cost']))
        for r in REPEATABLE_NODES:
            stacks = gs.purchased_repeatable.get(r['id'], 0)
            if can_purchase_repeatable(r, stacks, gs.current_dp, tier_cap):
                candidates.append(('rep', r, repeatable_cost(r, stacks)))
        if not candidates:
            break
        candidates.sort(key=lambda x: (x[2], x[1]['id']))
        kind, item, cost = candidates[0]
        if kind == 'skill':
            gs.current_dp -= cost
            gs.purchased_nodes.add(item['id'])
            if item['effect']['type'] == 'time':
                gs.extra_timer_secs += item['effect']['value']
        else:
            gs.current_dp -= cost
            gs.purchased_repeatable[item['id']] = gs.purchased_repeatable.get(item['id'], 0) + 1
        bought += 1
    if bought:
        recompute_stats()


def start_session_pure(disk_key: str) -> str:
    """Set up a fresh session on `disk_key`. Returns 'playing' for a normal session
    or 'auto_won' when Master legacy auto-clears the disk.

    Side effects on gs but no pygame/IO/save calls. Handles:
      - Master auto-clear (disks with order <= legacy_auto_clear_orders complete instantly)
      - Quick Start auto-buy (for the first N sessions after a prestige)
      - Increments sessions_since_prestige counter
    """
    gs.current_disk = disk_key

    # Master legacy: low-letter disks auto-complete on start
    order = DISK_ORDER.get(disk_key, 999)
    if order <= gs.legacy_auto_clear_orders:
        init_grid_for_disk(disk_key)
        # Mark everything as good (full clear)
        for row in gs.grid:
            for cell in row:
                cell.state = 'good'
        update_fragmentation()
        gs.session_cleaned = max(gs.session_cleaned, TOTAL_CELLS // 4)  # nominal reward base
        gs.sessions_since_prestige = min(gs.sessions_since_prestige + 1, 99999)
        end_session_pure(success=True)
        return 'auto_won'

    init_grid_for_disk(disk_key)
    gs.time_left = get_disk_timer(disk_key)
    gs.session_end_reason = ''
    gs.victory_celebration_until = 0.0

    # Quick Start: for the first N sessions after each prestige, auto-buy cheapest
    if (gs.legacy_quick_start_sessions > 0
            and gs.sessions_since_prestige < gs.legacy_quick_start_sessions):
        _quick_start_auto_buy()

    gs.sessions_since_prestige = min(gs.sessions_since_prestige + 1, 99999)
    return 'playing'


def end_session_pure(success: bool) -> tuple[int, int]:
    """Compute and apply session rewards. Returns (dp_gained, lp_gained). No IO."""
    gs.session_end_reason = 'DRIVE OPTIMIZED' if success else 'TIMED OUT'
    start_pct = DISKS[gs.current_disk]['start_frag'] * 100.0
    progress = max(0.0, (start_pct - gs.fragmentation) / max(0.01, start_pct))
    base = 40 if success else 14
    progress_mult = 36 if success else 22
    shatter_bonus_mult = 1.0 + gs.current_shatter_dp * gs.session_shatter_events
    dp_raw = (base + progress * progress_mult + gs.session_cleaned / 10.0) * shatter_bonus_mult * gs.current_dp_mult
    gs.earned_dp = int(dp_raw)
    gs.current_dp += gs.earned_dp

    gs.earned_lp = 0
    if success:
        # LP per disk: now 1× the order (was 2×) so the legacy tree doesn't max in 15 min.
        disk_lp = max(1, DISK_ORDER[gs.current_disk])
        gs.earned_lp = int((disk_lp + gs.session_cleaned // 500) * gs.current_lp_mult)
        gs.unspent_lp += gs.earned_lp
        curr_order = DISK_ORDER.get(gs.current_disk, 0)
        if curr_order > get_highest_cleared_order():
            gs.highest_disk_cleared = gs.current_disk

    if gs.prestige_count >= 1 and gs.current_dp < 5:
        gs.current_dp = 5

    return gs.earned_dp, gs.earned_lp


def perform_prestige_pure():
    """Apply prestige math: count, life-reset, legacy/stat recompute. No IO.

    Honors the new mechanic legacies:
      - DP Carryover keeps a % of current DP into the new life.
      - Veteran Operator adds (dp_per_prestige × prestige_count) starting DP.
      - Reset Mastery awards bonus LP on every prestige.
      - Inherit Stacks keeps a fraction of repeatable stacks across the reset.
      - Grandmaster grants free starting stacks per repeatable.
      - Sessions-since-prestige counter resets to 0 so Quick Start's window reactivates.
    """
    made_progress = gs.total_lifetime_cleaned >= (gs.prestige_lifetime_baseline + 100)
    if made_progress or gs.prestige_count == 0:
        gs.prestige_count += 1
        starting_dp = 3 + gs.prestige_count
    else:
        starting_dp = max(3, gs.current_dp)

    # Apply mechanic legacy bonuses BEFORE clearing per-life state
    carried_dp = int(gs.current_dp * gs.legacy_dp_carryover_pct) if gs.legacy_dp_carryover_pct > 0 else 0
    veteran_bonus = gs.legacy_dp_per_prestige * gs.prestige_count
    # Inherit Stacks — keep fraction of old repeatable stack counts
    if gs.legacy_inherit_stacks_pct > 0:
        kept_stacks = {nid: int(stacks * gs.legacy_inherit_stacks_pct)
                       for nid, stacks in gs.purchased_repeatable.items()}
        kept_stacks = {k: v for k, v in kept_stacks.items() if v > 0}
    else:
        kept_stacks = {}
    # Reset Mastery — LP bonus every prestige
    if gs.legacy_starting_lp > 0:
        gs.unspent_lp += gs.legacy_starting_lp

    gs.prestige_lifetime_baseline = gs.total_lifetime_cleaned
    gs.purchased_nodes = set()
    gs.purchased_repeatable = dict(kept_stacks)
    # Grandmaster — free starting stacks per repeatable (after inheritance)
    if gs.legacy_free_rep_stacks > 0:
        for r in REPEATABLE_NODES:
            existing = gs.purchased_repeatable.get(r['id'], 0)
            gs.purchased_repeatable[r['id']] = max(existing, gs.legacy_free_rep_stacks)
    gs.extra_timer_secs = 0
    gs.current_disk = 'C:'
    gs.session_end_reason = ''
    # Final starting DP after carryover + veteran
    gs.current_dp = starting_dp + carried_dp + veteran_bonus
    # Reset Quick Start window
    gs.sessions_since_prestige = 0

    recompute_legacy_bonuses()
    recompute_stats()
    init_grid_for_disk('C:')
    gs.time_left = get_disk_timer('C:')


# ----------------------------------------------------------------------------
# UI-side wrappers — same external behavior as before
# ----------------------------------------------------------------------------

def start_session(disk_key: str):
    status = start_session_pure(disk_key)
    if status == 'auto_won':
        # Master auto-clear already invoked end_session_pure; just transition state + save
        save_game(active_slot)
        set_state('HUB')
        set_hub_view('skill')
    else:
        set_state('PLAYING')


def end_session(success: bool):
    """Award rewards and pop the end-of-session modal. The dialog is dismissed via
    'continue_from_session' (Continue button / Enter / Esc), which actually transitions
    to HUB. Saving happens here so progress isn't lost if the player quits mid-dialog."""
    end_session_pure(success)
    save_game(active_slot)
    global show_end_dialog
    show_end_dialog = True


def perform_prestige():
    perform_prestige_pure()
    set_state('HUB')
    set_hub_view('skill')
    gs.prestige_banner_until = pygame.time.get_ticks() / 1000.0 + 5.5
    save_game(active_slot)


# ============================================================================
# PYGAME INIT
# ============================================================================

pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("DEFRAG.EXE - M1CROSOFT Windows")
clock = pygame.time.Clock()

# Win95-ish fonts. SysFont falls back to default if missing.
font      = pygame.font.SysFont("ms sans serif,tahoma,dejavu sans,arial", 14, bold=False)
font_bold = pygame.font.SysFont("ms sans serif,tahoma,dejavu sans,arial", 14, bold=True)
font_big  = pygame.font.SysFont("ms sans serif,tahoma,dejavu sans,arial", 18, bold=True)
font_huge = pygame.font.SysFont("ms sans serif,tahoma,dejavu sans,arial", 26, bold=True)
font_tiny = pygame.font.SysFont("ms sans serif,tahoma,dejavu sans,arial", 11, bold=False)


# ============================================================================
# WIN95 DRAWING PRIMITIVES
# ============================================================================

def draw_bevel(rect: pygame.Rect, raised: bool = True, outer: bool = True):
    """Draw a Win95 bevel: raised (top/left light, bottom/right shadow) or sunken (inverted).
    `outer` adds an outer dark hairline (used by raised buttons)."""
    x, y, w, h = rect
    if raised:
        # Outer dark line
        if outer:
            pygame.draw.rect(screen, W95_DARK, rect, 1)
            inner = pygame.Rect(x + 1, y + 1, w - 2, h - 2)
        else:
            inner = rect
        ix, iy, iw, ih = inner
        # Light top + left
        pygame.draw.line(screen, W95_LIGHT, (ix, iy), (ix + iw - 1, iy), 1)
        pygame.draw.line(screen, W95_LIGHT, (ix, iy), (ix, iy + ih - 1), 1)
        # Shadow bottom + right
        pygame.draw.line(screen, W95_SHADOW, (ix, iy + ih - 1), (ix + iw - 1, iy + ih - 1), 1)
        pygame.draw.line(screen, W95_SHADOW, (ix + iw - 1, iy), (ix + iw - 1, iy + ih - 1), 1)
    else:
        # Sunken: shadow top+left, light bottom+right
        pygame.draw.line(screen, W95_SHADOW, (x, y), (x + w - 1, y), 1)
        pygame.draw.line(screen, W95_SHADOW, (x, y), (x, y + h - 1), 1)
        pygame.draw.line(screen, W95_LIGHT, (x, y + h - 1), (x + w - 1, y + h - 1), 1)
        pygame.draw.line(screen, W95_LIGHT, (x + w - 1, y), (x + w - 1, y + h - 1), 1)


def draw_panel(rect: pygame.Rect, face=W95_FACE, raised: bool = True):
    pygame.draw.rect(screen, face, rect)
    draw_bevel(rect, raised=raised, outer=raised)


def draw_button(rect: pygame.Rect, label: str, enabled: bool = True,
                pressed: bool = False, hovered: bool = False, font_obj=None) -> None:
    f = font_obj or font
    pygame.draw.rect(screen, W95_FACE, rect)
    if pressed and enabled:
        draw_bevel(rect, raised=False)
    else:
        draw_bevel(rect, raised=True)
    text_color = W95_TEXT if enabled else W95_TEXT_DISABLED
    surf = f.render(label, True, text_color)
    # Disabled "etched" look: draw white shadow underneath
    if not enabled:
        white = f.render(label, True, W95_LIGHT)
        screen.blit(white, (rect.x + (rect.w - white.get_width()) // 2 + 1,
                            rect.y + (rect.h - white.get_height()) // 2 + 1))
    screen.blit(surf, (rect.x + (rect.w - surf.get_width()) // 2 + (1 if pressed else 0),
                       rect.y + (rect.h - surf.get_height()) // 2 + (1 if pressed else 0)))
    if hovered and enabled:
        # focus rect: dotted dark
        focus = rect.inflate(-6, -6)
        for i in range(focus.x, focus.x + focus.w, 2):
            screen.set_at((i, focus.y), W95_DARK)
            screen.set_at((i, focus.y + focus.h - 1), W95_DARK)
        for j in range(focus.y, focus.y + focus.h, 2):
            screen.set_at((focus.x, j), W95_DARK)
            screen.set_at((focus.x + focus.w - 1, j), W95_DARK)


def draw_titlebar(rect: pygame.Rect, title: str, active: bool = True,
                  show_min: bool = True, show_close: bool = True):
    """Win95 gradient titlebar with optional min/close glyphs."""
    base = W95_TITLE_ACTIVE if active else W95_TITLE_INACTIVE
    grad_end = W95_TITLE_GRAD if active else (170, 170, 170)
    # 2-stop gradient
    for i in range(rect.w):
        t = i / max(1, rect.w - 1)
        c = (int(base[0] + (grad_end[0] - base[0]) * t),
             int(base[1] + (grad_end[1] - base[1]) * t),
             int(base[2] + (grad_end[2] - base[2]) * t))
        pygame.draw.line(screen, c, (rect.x + i, rect.y), (rect.x + i, rect.y + rect.h - 1), 1)
    surf = font_bold.render(title, True, W95_TITLE_TEXT)
    screen.blit(surf, (rect.x + 4, rect.y + (rect.h - surf.get_height()) // 2))
    # Buttons on the right
    btn_w = rect.h - 6
    bx = rect.x + rect.w - btn_w - 3
    if show_close:
        cb = pygame.Rect(bx, rect.y + 3, btn_w, btn_w)
        draw_panel(cb, raised=True)
        x0, y0, x1, y1 = cb.x + 4, cb.y + 4, cb.right - 4, cb.bottom - 4
        pygame.draw.line(screen, W95_DARK, (x0, y0), (x1, y1), 2)
        pygame.draw.line(screen, W95_DARK, (x0, y1), (x1, y0), 2)
        bx -= btn_w + 2
    if show_min:
        mb = pygame.Rect(bx, rect.y + 3, btn_w, btn_w)
        draw_panel(mb, raised=True)
        pygame.draw.line(screen, W95_DARK, (mb.x + 3, mb.bottom - 5),
                         (mb.right - 4, mb.bottom - 5), 2)


def draw_window(rect: pygame.Rect, title: str, active: bool = True,
                show_min: bool = True, show_close: bool = True) -> pygame.Rect:
    """Draw a Win95 window frame with titlebar. Returns the inner client rect."""
    # Outer frame
    pygame.draw.rect(screen, W95_FACE, rect)
    draw_bevel(rect, raised=True)
    # Titlebar
    tb = pygame.Rect(rect.x + WINDOW_BORDER, rect.y + WINDOW_BORDER,
                     rect.w - 2 * WINDOW_BORDER, TITLEBAR_H)
    draw_titlebar(tb, title, active=active, show_min=show_min, show_close=show_close)
    # Client area
    client = pygame.Rect(rect.x + WINDOW_BORDER, tb.bottom + 1,
                         rect.w - 2 * WINDOW_BORDER,
                         rect.h - TITLEBAR_H - 2 * WINDOW_BORDER - 1)
    return client


def draw_progress_bar(rect: pygame.Rect, fraction: float, segments: bool = True):
    """Win95 segmented progress bar (sunken trough, navy blocks)."""
    draw_bevel(rect, raised=False, outer=False)
    pygame.draw.rect(screen, W95_FACE, rect.inflate(-2, -2))
    inner = rect.inflate(-4, -4)
    fill_w = int(inner.w * max(0.0, min(1.0, fraction)))
    if segments:
        seg_w = 8
        gap = 2
        x = inner.x
        while x + seg_w <= inner.x + fill_w:
            pygame.draw.rect(screen, W95_TITLE_ACTIVE, (x, inner.y, seg_w, inner.h))
            x += seg_w + gap
    else:
        pygame.draw.rect(screen, W95_TITLE_ACTIVE, (inner.x, inner.y, fill_w, inner.h))


def draw_taskbar(active_state: str):
    """Faux Win95 taskbar with Start button + active program tab + clock."""
    bar = pygame.Rect(0, WINDOW_HEIGHT - TASKBAR_H, WINDOW_WIDTH, TASKBAR_H)
    pygame.draw.rect(screen, W95_FACE, bar)
    # Top bevel line only
    pygame.draw.line(screen, W95_LIGHT, (0, bar.y), (bar.right, bar.y), 1)
    pygame.draw.line(screen, W95_SHADOW, (0, bar.y + 1), (bar.right, bar.y + 1), 1)

    # Start button
    sb = pygame.Rect(4, bar.y + 3, 74, TASKBAR_H - 6)
    draw_panel(sb, raised=True)
    flag = font_bold.render("Start", True, W95_TEXT)
    # tiny window-flag glyph
    pygame.draw.rect(screen, (255, 0, 0), (sb.x + 6, sb.y + 6, 5, 5))
    pygame.draw.rect(screen, (0, 192, 0), (sb.x + 12, sb.y + 6, 5, 5))
    pygame.draw.rect(screen, (0, 0, 192), (sb.x + 6, sb.y + 12, 5, 5))
    pygame.draw.rect(screen, (255, 255, 0), (sb.x + 12, sb.y + 12, 5, 5))
    screen.blit(flag, (sb.x + 24, sb.y + 4))

    # Active program tab
    label = {
        'TITLE': 'Welcome',
        'MENU': 'DEFRAG.EXE',
        'HUB': 'Defragmenter Hub',
        'PRESTIGE': 'Prestige',
        'PLAYING': f'Defragmenting Drive {gs.current_disk}',
        'SETTINGS': 'Settings',
        'LOAD': 'Load Game',
    }.get(active_state, 'DEFRAG.EXE')
    tab = pygame.Rect(86, bar.y + 3, 220, TASKBAR_H - 6)
    draw_panel(tab, raised=False)
    surf = font.render(label, True, W95_TEXT)
    screen.blit(surf, (tab.x + 10, tab.y + 4))

    # Clock area (right) — system tray bevel. Synced to the real system clock (local time).
    tray = pygame.Rect(bar.right - 88, bar.y + 3, 84, TASKBAR_H - 6)
    draw_panel(tray, raised=False)
    now_local = time.localtime()
    ampm = 'AM' if now_local.tm_hour < 12 else 'PM'
    h12 = now_local.tm_hour % 12 or 12
    clk = font.render(f"{h12:2d}:{now_local.tm_min:02d} {ampm}", True, W95_TEXT)
    screen.blit(clk, (tray.x + 10, tray.y + 4))


# ============================================================================
# STATE / SCREEN HELPERS
# ============================================================================

# Game screen state machine
game_state = 'TITLE'     # TITLE | MENU | HUB | PLAYING | SETTINGS | LOAD | PRESTIGE
prev_state = 'TITLE'
hub_view = 'skill'       # 'skill' | 'prestige'
active_slot = 1

# Transient UI state — not persisted in saves
is_paused: bool = False        # Pause button / P key — freezes session tick + click input
show_legend: bool = False      # Legend button / L key — overlays the Legend dialog
hide_details: bool = False     # Hide Details button — toggles the bottom stats line
show_end_dialog: bool = False  # End-of-session modal — set when end_session fires, cleared on acknowledge

# Per-frame collected clickable rects: (rect, action, payload)
buttons: list[tuple[pygame.Rect, str, object]] = []
pressed_button = None    # rect we're currently mouse-down on (for pressed visual)


def set_state(s: str):
    global game_state, prev_state
    prev_state = game_state
    game_state = s
    buttons.clear()


def set_hub_view(v: str):
    global hub_view
    hub_view = v


def reset_for_new_game():
    """Wipe per-game state for New Game (slot is fresh). Gives starter DP so first attempt isn't bare-handed."""
    global gs
    gs = GameState()
    gs.current_dp = NEW_GAME_STARTER_DP
    recompute_legacy_bonuses()
    recompute_stats()
    init_grid_for_disk('C:')
    gs.time_left = get_disk_timer('C:')


# ============================================================================
# DRAW: BACKDROP + DEFRAG GRID
# ============================================================================

def draw_desktop():
    screen.fill(W95_DESKTOP)


def draw_defrag_grid(rect: pygame.Rect, dim: bool = False):
    """Render the cell grid inside an arbitrary rect. Win95 navy field with chunky cells."""
    pygame.draw.rect(screen, DEFRAG_FIELD, rect)
    pygame.draw.rect(screen, DEFRAG_FRAME, rect, 1)
    cell_w = (rect.w - 4) // GRID_COLS
    cell_h = (rect.h - 4) // GRID_ROWS
    if cell_w < 4: cell_w = 4
    if cell_h < 4: cell_h = 4
    ox = rect.x + 2 + (rect.w - 4 - cell_w * GRID_COLS) // 2
    oy = rect.y + 2 + (rect.h - 4 - cell_h * GRID_ROWS) // 2

    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            cell = gs.grid[r][c]
            if cell.state == 'fragmented':
                if cell.file_type == 'temp':  col = FRAG_TEMP
                elif cell.file_type == 'doc': col = FRAG_DOC
                elif cell.file_type == 'media': col = FRAG_MEDIA
                else: col = FRAG_SYS
            else:
                col = DEFRAG_GOOD
            if dim:
                col = (col[0] // 2, col[1] // 2, col[2] // 2 + 30)
            pygame.draw.rect(screen, col, (ox + c * cell_w, oy + r * cell_h, cell_w - 4, cell_h - 4))

    # Transient highlight outlines for cells that just changed state.
    # Drawn AFTER the base cells (covers their edge) and prunes expired entries inline.
    now = pygame.time.get_ticks() / 1000.0
    expired = []
    for (hr, hc), expire_at in gs.cell_highlights.items():
        if expire_at <= now:
            expired.append((hr, hc))
            continue
        if not (0 <= hr < GRID_ROWS and 0 <= hc < GRID_COLS):
            expired.append((hr, hc))
            continue
        # 2-pixel Win95-grey outline drawn slightly outside the cell content so it lights
        # up the navy gap rather than overwriting the cell color.
        hx = ox + hc * cell_w - 1
        hy = oy + hr * cell_h - 1
        pygame.draw.rect(screen, HIGHLIGHT_BORDER, (hx, hy, cell_w - 1, cell_h - 1), 2)
    for k in expired:
        gs.cell_highlights.pop(k, None)


def get_grid_rect_in_window(client: pygame.Rect) -> pygame.Rect:
    """The drawing area for the defrag cells inside a window's client rect."""
    return pygame.Rect(client.x + 8, client.y + 8, client.w - 16, client.h - 70)


def cell_at_pixel(grid_rect: pygame.Rect, px: int, py: int) -> tuple[int, int] | None:
    cell_w = (grid_rect.w - 4) // GRID_COLS
    cell_h = (grid_rect.h - 4) // GRID_ROWS
    if cell_w < 4: cell_w = 4
    if cell_h < 4: cell_h = 4
    ox = grid_rect.x + 2 + (grid_rect.w - 4 - cell_w * GRID_COLS) // 2
    oy = grid_rect.y + 2 + (grid_rect.h - 4 - cell_h * GRID_ROWS) // 2
    if not (ox <= px < ox + cell_w * GRID_COLS and oy <= py < oy + cell_h * GRID_ROWS):
        return None
    return (px - ox) // cell_w, (py - oy) // cell_h


# ============================================================================
# DRAW: TITLE / MENU / LOAD / SETTINGS
# ============================================================================

def draw_title_screen():
    draw_desktop()
    # Centered Win95 window
    w, h = 540, 360
    win = pygame.Rect((WINDOW_WIDTH - w) // 2, (WINDOW_HEIGHT - h) // 2 - 20, w, h)
    client = draw_window(win, "DEFRAG.EXE - M1CROSOFT Windows")

    # Big block logo
    logo = font_huge.render("DEFRAG.EXE", True, W95_TEXT)
    screen.blit(logo, (client.x + (client.w - logo.get_width()) // 2, client.y + 24))
    sub = font.render("M1CROSOFT Disk Defragmenter — Idle Edition", True, W95_TEXT_DIM)
    screen.blit(sub, (client.x + (client.w - sub.get_width()) // 2, client.y + 60))

    bx = client.x + (client.w - 220) // 2
    by = client.y + 110
    spacing = 36

    items = [
        ('new_game', 'New Game'),
        ('load_menu', 'Load Game'),
        ('settings', 'Settings'),
        ('quit', 'Exit'),
    ]
    mx, my = pygame.mouse.get_pos()
    for action, label in items:
        rect = pygame.Rect(bx, by, 220, 28)
        buttons.append((rect, action, None))
        hov = rect.collidepoint(mx, my)
        prs = (pressed_button == rect)
        draw_button(rect, label, enabled=True, pressed=prs, hovered=hov)
        by += spacing

    foot = font_tiny.render("(c) 1995 M1CROSOFT Corporation - Prototype Build", True, W95_TEXT_DIM)
    screen.blit(foot, (client.x + (client.w - foot.get_width()) // 2, client.bottom - 22))


def draw_load_screen():
    draw_desktop()
    w, h = 620, 380
    win = pygame.Rect((WINDOW_WIDTH - w) // 2, (WINDOW_HEIGHT - h) // 2 - 20, w, h)
    client = draw_window(win, "Load Game")

    hdr = font_bold.render("Select a save slot:", True, W95_TEXT)
    screen.blit(hdr, (client.x + 16, client.y + 12))

    mx, my = pygame.mouse.get_pos()
    sy = client.y + 38
    for slot in (1, 2, 3):
        s = slot_summary(slot)
        row = pygame.Rect(client.x + 16, sy, client.w - 32, 60)
        draw_panel(row, raised=False)
        if s:
            text = f"Slot {slot}: Highest {s['highest']}  •  Prestige #{s['prestige']}  •  {s['cleaned']:,} cleaned"
            screen.blit(font_bold.render(text, True, W95_TEXT), (row.x + 10, row.y + 8))
            screen.blit(font_tiny.render(f"File: {slot_path(slot)}", True, W95_TEXT_DIM), (row.x + 10, row.y + 30))
            # Load + Delete buttons
            lb = pygame.Rect(row.right - 168, row.y + 16, 76, 26)
            db = pygame.Rect(row.right - 84,  row.y + 16, 76, 26)
            buttons.append((lb, 'load_slot', slot))
            buttons.append((db, 'delete_slot', slot))
            draw_button(lb, "Load", True, pressed_button == lb, lb.collidepoint(mx, my))
            draw_button(db, "Delete", True, pressed_button == db, db.collidepoint(mx, my))
        else:
            screen.blit(font.render(f"Slot {slot}: (empty)", True, W95_TEXT_DIM), (row.x + 10, row.y + 20))
            nb = pygame.Rect(row.right - 100, row.y + 16, 84, 26)
            buttons.append((nb, 'new_in_slot', slot))
            draw_button(nb, "New Game", True, pressed_button == nb, nb.collidepoint(mx, my))
        sy += 70

    back = pygame.Rect(client.x + 16, client.bottom - 38, 110, 26)
    buttons.append((back, 'back_title', None))
    draw_button(back, "Back", True, pressed_button == back, back.collidepoint(mx, my))


def _format_file_size(num_bytes: int) -> str:
    """Compact KB/MB rendering for save-file size display."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def draw_settings_screen():
    draw_desktop()
    w, h = 580, 510
    win = pygame.Rect((WINDOW_WIDTH - w) // 2, (WINDOW_HEIGHT - h) // 2 - 20, w, h)
    client = draw_window(win, "Settings")
    mx, my = pygame.mouse.get_pos()

    y = client.y + 14

    # ===== ABOUT =====
    screen.blit(font_bold.render("About", True, W95_TEXT), (client.x + 14, y))
    y += font_bold.get_height() + 4
    about_box = pygame.Rect(client.x + 14, y, client.w - 28, 92)
    draw_panel(about_box, raised=False)
    ay = about_box.y + 8
    screen.blit(font_huge.render("DEFRAG.EXE", True, W95_TITLE_ACTIVE), (about_box.x + 12, ay))
    ay += font_huge.get_height() - 2
    screen.blit(font.render("A Win95-styled defragmenter clicker / idler", True, W95_TEXT),
                (about_box.x + 12, ay))
    ay += font.get_height() + 2
    screen.blit(font_bold.render("Created by Jim", True, W95_TEXT), (about_box.x + 12, ay))
    y = about_box.bottom + 12

    # ===== SAVES =====
    screen.blit(font_bold.render("Save data", True, W95_TEXT), (client.x + 14, y))
    y += font_bold.get_height() + 4
    saves_box = pygame.Rect(client.x + 14, y, client.w - 28, 162)
    draw_panel(saves_box, raised=False)
    sy = saves_box.y + 6
    # Save directory path (truncate if too long)
    path_str = str(save_dir())
    if font.size(path_str)[0] > saves_box.w - 100:
        path_str = "..." + path_str[-50:]
    screen.blit(font.render(f"Location:  {path_str}", True, W95_TEXT), (saves_box.x + 8, sy))
    sy += font.get_height() + 4
    screen.blit(font.render(f"Active slot:  {active_slot}", True, W95_TEXT), (saves_box.x + 8, sy))
    sy += font.get_height() + 6
    # Slot table — one row per slot with summary + file size
    for slot in (1, 2, 3):
        summary = slot_summary(slot)
        path = slot_path(slot)
        try:
            fsize = path.stat().st_size if path.exists() else 0
        except OSError:
            fsize = 0
        row_rect = pygame.Rect(saves_box.x + 8, sy, saves_box.w - 16, 22)
        # Visual highlight on active slot
        if slot == active_slot:
            pygame.draw.rect(screen, (220, 220, 200), row_rect)
            pygame.draw.rect(screen, (140, 140, 100), row_rect, 1)
        if summary:
            text = (f"Slot {slot}:  highest {summary['highest']}   "
                    f"Prestige #{summary['prestige']}   "
                    f"{summary['cleaned']:,} cleaned   ({_format_file_size(fsize)})")
        else:
            text = f"Slot {slot}:  (empty)"
        screen.blit(font.render(text, True, W95_TEXT), (row_rect.x + 6, row_rect.y + 4))
        sy += row_rect.h + 2
    y = saves_box.bottom + 10

    # ===== Hotkeys reference (functional info — these really do work in-game) =====
    screen.blit(font_bold.render("Hotkeys (in-session)", True, W95_TEXT), (client.x + 14, y))
    y += font_bold.get_height() + 4
    keys_box = pygame.Rect(client.x + 14, y, client.w - 28, 64)
    draw_panel(keys_box, raised=False)
    ky = keys_box.y + 6
    hotkeys = [
        "Space / click grid — manual defrag sweep",
        "P — pause / resume        L — toggle legend",
        "B — bail to hub          Enter — buy selected node (in trees) / continue dialog",
    ]
    for ln in hotkeys:
        screen.blit(font_tiny.render(ln, True, W95_TEXT), (keys_box.x + 10, ky))
        ky += font_tiny.get_height() + 2

    # OK button anchored to bottom
    back = pygame.Rect(client.x + (client.w - 120) // 2, client.bottom - 38, 120, 28)
    buttons.append((back, 'back_title', None))
    draw_button(back, "OK", True, pressed_button == back, back.collidepoint(mx, my), font_obj=font_bold)


# ============================================================================
# DRAW: HUB (between rounds — skill tree + prestige tabs + disk selection)
# ============================================================================

# ============================================================================
# TREE-VIEW UI STATE (Win95 Registry Editor style)
# ============================================================================

ROMAN_TIERS = {'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'}

SKILL_BRANCH_ORDER = [
    ('manual', 'MANUAL'),
    ('click', 'CLICK'),
    ('auto', 'AUTO'),
    ('fs', 'FILESYSTEM'),
]
LEGACY_BRANCH_ORDER = [
    ('manual', 'MANUAL'),
    ('click', 'CLICK'),
    ('auto', 'AUTO'),
    ('time', 'TIME'),
    ('knowledge', 'KNOWLEDGE'),
    ('scaling', 'SCALING'),
]

# Branches expand by default so the player sees structure on first open;
# lines (families) stay collapsed for a compact initial view.
tree_expanded: set = {b for b, _ in SKILL_BRANCH_ORDER} | {('legacy', b) for b, _ in LEGACY_BRANCH_ORDER}
tree_selected_skill_id: str | None = None
tree_selected_legacy_id: str | None = None
tree_scroll_skill: int = 0
tree_scroll_legacy: int = 0
TREE_ROW_H = 18


def family_of(node):
    """'Power IV' -> 'Power'. 'Macro Recorder II' -> 'Macro Recorder'. Strips roman-numeral tier suffix."""
    parts = node['name'].split(' ')
    if len(parts) > 1 and parts[-1] in ROMAN_TIERS:
        return ' '.join(parts[:-1])
    return node['name']


def _node_status_color(node, owned_set, currency, tier_cap, is_legacy: bool):
    if node['id'] in owned_set:
        return (40, 160, 40)        # green: owned
    if is_legacy:
        tier_ok = True
        cost = effective_legacy_cost(node)
    else:
        effective_req = max(1, node.get('tier', 1) - gs.legacy_tier_offset)
        tier_ok = effective_req <= tier_cap
        cost = node['cost']
    prereqs_ok = all(p in owned_set for p in node.get('prereqs', []))
    if not tier_ok or not prereqs_ok:
        return (170, 60, 60)        # red: locked
    if currency >= cost:
        return (230, 200, 50)       # yellow: ready to buy
    return (170, 170, 170)          # gray: prereqs met but unaffordable


def build_skill_tree_rows():
    """Flatten skill + repeatable nodes into a renderable row list, honoring expansion state."""
    rows = []
    grouped = {}  # branch -> {family -> [nodes]}
    for n in SKILL_NODES:
        grouped.setdefault(n['branch'], {}).setdefault(family_of(n), []).append(n)
    for fams in grouped.values():
        for nodes in fams.values():
            nodes.sort(key=lambda x: (x['tier'], x['cost']))

    # Bucket repeatable nodes by branch for inclusion
    reps_by_branch = {}
    for r in REPEATABLE_NODES:
        reps_by_branch.setdefault(r['branch'], []).append(r)

    for b_key, b_label in SKILL_BRANCH_ORDER:
        if b_key not in grouped and b_key not in reps_by_branch:
            continue
        b_expanded = b_key in tree_expanded
        rows.append({'kind': 'branch', 'indent': 0, 'label': b_label, 'key': b_key, 'expanded': b_expanded})
        if not b_expanded:
            continue
        # Fixed-node families
        for family in sorted(grouped.get(b_key, {}).keys()):
            line_key = (b_key, family)
            line_expanded = line_key in tree_expanded
            nodes_in_line = grouped[b_key][family]
            owned_n = sum(1 for n in nodes_in_line if n['id'] in gs.purchased_nodes)
            rows.append({
                'kind': 'line', 'indent': 1,
                'label': f"{family}  ({owned_n}/{len(nodes_in_line)})",
                'key': line_key, 'expanded': line_expanded,
            })
            if not line_expanded:
                continue
            for node in nodes_in_line:
                rows.append({'kind': 'node', 'indent': 2, 'label': node['name'], 'node': node, 'is_legacy': False})
        # Repeatable nodes — shown at indent 1 (sibling of family headers) so they stand out
        for rep in reps_by_branch.get(b_key, []):
            stacks = gs.purchased_repeatable.get(rep['id'], 0)
            label = f"※ {rep['name']}  ({stacks}/{rep['max_stacks']})"
            rows.append({
                'kind': 'repeatable', 'indent': 1,
                'label': label, 'node': rep,
                'stacks': stacks,
                'cur_cost': repeatable_cost(rep, stacks),
            })
    return rows


def build_legacy_tree_rows():
    """Build legacy tree rows. Filters out milestone-gated nodes whose min_prestige_count
    threshold isn't met yet — they stay hidden so the tree size grows as you prestige deeper."""
    rows = []
    grouped = {}
    for n in LEGACY_NODES:
        # Hide milestone-gated nodes the player hasn't unlocked yet
        min_pc = n.get('min_prestige_count', 0)
        if gs.prestige_count < min_pc:
            continue
        grouped.setdefault(n['branch'], []).append(n)
    for b_key, b_label in LEGACY_BRANCH_ORDER:
        if b_key not in grouped:
            continue
        leg_key = ('legacy', b_key)
        b_expanded = leg_key in tree_expanded
        owned_n = sum(1 for n in grouped[b_key] if n['id'] in gs.purchased_legacy)
        rows.append({
            'kind': 'branch', 'indent': 0,
            'label': f"{b_label}  ({owned_n}/{len(grouped[b_key])})",
            'key': leg_key, 'expanded': b_expanded,
        })
        if not b_expanded:
            continue
        for node in grouped[b_key]:
            rows.append({'kind': 'node', 'indent': 1, 'label': node['name'], 'node': node, 'is_legacy': True})
    return rows


def draw_tree_pane(rect: pygame.Rect, rows: list, scroll: int, selected_id: str | None, on_select_action: str) -> int:
    """Render the scrolling tree-view. Returns clamped scroll value."""
    draw_panel(rect, raised=False)
    inner = rect.inflate(-4, -4)

    # Win95 list-view header bar
    header = pygame.Rect(inner.x, inner.y, inner.w, 18)
    pygame.draw.rect(screen, W95_FACE, header)
    pygame.draw.line(screen, W95_LIGHT, (header.x, header.y), (header.right, header.y), 1)
    pygame.draw.line(screen, W95_SHADOW, (header.x, header.bottom - 1), (header.right, header.bottom - 1), 1)
    # Name column header (with right-side beveled separator just to feel right)
    screen.blit(font_bold.render("Name", True, W95_TEXT), (header.x + 6, header.y + 2))
    cost_hdr_x = header.right - 90
    pygame.draw.line(screen, W95_SHADOW, (cost_hdr_x - 2, header.y + 2), (cost_hdr_x - 2, header.bottom - 3), 1)
    pygame.draw.line(screen, W95_LIGHT,  (cost_hdr_x - 1, header.y + 2), (cost_hdr_x - 1, header.bottom - 3), 1)
    screen.blit(font_bold.render("Cost", True, W95_TEXT), (cost_hdr_x + 4, header.y + 2))

    list_area = pygame.Rect(inner.x, header.bottom, inner.w, inner.h - 18)
    pygame.draw.rect(screen, W95_LIGHT, list_area)  # white interior like a Win95 list

    # Clamp scroll
    total_h = len(rows) * TREE_ROW_H
    max_scroll = max(0, total_h - list_area.h)
    scroll = max(0, min(scroll, max_scroll))

    # Scrollbar reservation
    needs_sb = total_h > list_area.h
    sb_w = 14 if needs_sb else 0
    rows_area = pygame.Rect(list_area.x, list_area.y, list_area.w - sb_w, list_area.h)

    prev_clip = screen.get_clip()
    screen.set_clip(rows_area)

    start_idx = max(0, scroll // TREE_ROW_H)
    y_offset = -(scroll % TREE_ROW_H)
    tier_cap = get_unlocked_tier()

    for i in range(start_idx, min(len(rows), start_idx + (rows_area.h // TREE_ROW_H) + 3)):
        row = rows[i]
        y = rows_area.y + y_offset + (i - start_idx) * TREE_ROW_H
        row_rect = pygame.Rect(rows_area.x, y, rows_area.w, TREE_ROW_H)

        is_selected = (row['kind'] == 'node' and selected_id is not None and row['node']['id'] == selected_id)
        if is_selected:
            pygame.draw.rect(screen, W95_SELECT_BG, row_rect)
            text_color = W95_SELECT_TEXT
        else:
            text_color = W95_TEXT

        # Tree connector lines (subtle dotted vertical to suggest hierarchy)
        for ind_lvl in range(row['indent']):
            cx = rows_area.x + 8 + ind_lvl * 14
            for dot_y in range(y, y + TREE_ROW_H, 2):
                if not is_selected:
                    screen.set_at((cx, dot_y), W95_SHADOW)

        x = rows_area.x + 4 + row['indent'] * 14

        if row['kind'] in ('branch', 'line'):
            # +/- glyph
            gw = 11
            glyph = pygame.Rect(x, y + 3, gw, gw)
            pygame.draw.rect(screen, W95_LIGHT, glyph)
            pygame.draw.rect(screen, W95_TEXT, glyph, 1)
            pygame.draw.line(screen, W95_TEXT, (glyph.x + 2, glyph.centery), (glyph.right - 3, glyph.centery), 1)
            if not row['expanded']:
                pygame.draw.line(screen, W95_TEXT, (glyph.centerx, glyph.y + 2), (glyph.centerx, glyph.bottom - 3), 1)
            x += gw + 4
            label_font = font_bold if row['kind'] == 'branch' else font
            screen.blit(label_font.render(row['label'], True, text_color), (x, y + 1))
            buttons.append((row_rect, 'toggle_tree', row['key']))
        elif row['kind'] == 'repeatable':
            # Repeatable node — current-stack price, capped by max_stacks
            icon = pygame.Rect(x + 2, y + 3, 11, 11)
            rep = row['node']
            stacks = row['stacks']
            cur_cost = row['cur_cost']
            # Status color: green if max'd, yellow if buyable, gray if unaffordable, red if tier-locked
            tier_ok = rep.get('tier', 99) <= tier_cap
            if stacks >= rep['max_stacks']:
                col = (40, 160, 40)   # green: fully owned
            elif not tier_ok:
                col = (170, 60, 60)   # red: locked
            elif gs.current_dp >= cur_cost:
                col = (230, 200, 50)  # yellow: buyable
            else:
                col = (170, 170, 170) # gray
            pygame.draw.rect(screen, col, icon)
            pygame.draw.rect(screen, W95_DARK, icon, 1)
            x += 16
            screen.blit(font_bold.render(row['label'], True, text_color), (x, y + 1))
            cost_str = f"{cur_cost} DP" if stacks < rep['max_stacks'] else "MAX"
            cost_col = text_color if is_selected else W95_TEXT_DIM
            cost_surf = font.render(cost_str, True, cost_col)
            screen.blit(cost_surf, (rows_area.right - cost_surf.get_width() - 6, y + 1))
            buttons.append((row_rect, on_select_action, rep['id']))
        else:  # node
            # Status icon
            icon = pygame.Rect(x + 2, y + 3, 11, 11)
            is_legacy = row.get('is_legacy', False)
            owned_set = gs.purchased_legacy if is_legacy else gs.purchased_nodes
            currency = gs.unspent_lp if is_legacy else gs.current_dp
            col = _node_status_color(row['node'], owned_set, currency, tier_cap, is_legacy)
            pygame.draw.rect(screen, col, icon)
            pygame.draw.rect(screen, W95_DARK, icon, 1)
            x += 16
            screen.blit(font.render(row['label'], True, text_color), (x, y + 1))
            # Cost on the right column — legacy costs honor Architect discount
            displayed_cost = effective_legacy_cost(row['node']) if is_legacy else row['node']['cost']
            cost_str = f"{displayed_cost} {'LP' if is_legacy else 'DP'}"
            cost_col = text_color if is_selected else W95_TEXT_DIM
            cost_surf = font.render(cost_str, True, cost_col)
            screen.blit(cost_surf, (rows_area.right - cost_surf.get_width() - 6, y + 1))
            buttons.append((row_rect, on_select_action, row['node']['id']))

    screen.set_clip(prev_clip)

    # Scrollbar (Win95 style)
    if needs_sb:
        sb_rect = pygame.Rect(list_area.right - sb_w, list_area.y, sb_w, list_area.h)
        pygame.draw.rect(screen, W95_FACE, sb_rect)
        thumb_h = max(20, int(sb_rect.h * (list_area.h / total_h)))
        thumb_y = sb_rect.y + (int((sb_rect.h - thumb_h) * (scroll / max_scroll)) if max_scroll > 0 else 0)
        thumb = pygame.Rect(sb_rect.x + 1, thumb_y, sb_rect.w - 2, thumb_h)
        pygame.draw.rect(screen, W95_FACE_DIM, thumb)
        draw_bevel(thumb, raised=True, outer=False)

    return scroll


def _wrap_text(text: str, font_obj, max_w: int) -> list[str]:
    """Greedy word-wrap for the inspector description."""
    if not text:
        return []
    words = text.split(' ')
    lines = []
    cur = ''
    for w in words:
        candidate = (cur + ' ' + w) if cur else w
        if font_obj.size(candidate)[0] <= max_w:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_inspector(rect: pygame.Rect, mx: int, my: int, selected_id: str | None, is_legacy: bool):
    """Right-hand 'Properties' panel for the currently selected tree node."""
    draw_panel(rect, raised=True)

    # Inner title strip (like a window header inside the panel)
    title_bar = pygame.Rect(rect.x + 3, rect.y + 3, rect.w - 6, 18)
    pygame.draw.rect(screen, W95_FACE_DIM, title_bar)
    pygame.draw.line(screen, W95_SHADOW, (title_bar.x, title_bar.bottom - 1), (title_bar.right, title_bar.bottom - 1), 1)
    screen.blit(font_bold.render("Properties", True, W95_TEXT), (title_bar.x + 6, title_bar.y + 2))

    body = pygame.Rect(rect.x + 10, title_bar.bottom + 8, rect.w - 20, rect.h - title_bar.h - 14)

    if not selected_id:
        screen.blit(font.render("(no item selected)", True, W95_TEXT_DIM), (body.x, body.y + 6))
        msg = "Click an upgrade on the left to see its details." if not is_legacy \
              else "Click a Legacy node on the left to see its details."
        for i, ln in enumerate(_wrap_text(msg, font, body.w)):
            screen.blit(font.render(ln, True, W95_TEXT_DIM), (body.x, body.y + 26 + i * 16))
        return

    # Repeatable nodes share the skill ID namespace from the player's perspective;
    # check that table first when we're in the skill tab.
    is_repeatable = (not is_legacy) and selected_id in REPEATABLE_BY_ID
    if is_repeatable:
        _draw_inspector_repeatable(rect, mx, my, selected_id, body)
        return

    node_db = LEGACY_BY_ID if is_legacy else SKILL_BY_ID
    node = node_db.get(selected_id)
    if not node:
        screen.blit(font.render("(node missing)", True, W95_TEXT_DIM), (body.x, body.y + 6))
        return

    purchased = gs.purchased_legacy if is_legacy else gs.purchased_nodes
    currency = gs.unspent_lp if is_legacy else gs.current_dp
    currency_name = 'LP' if is_legacy else 'DP'
    tier_cap = get_unlocked_tier()

    owned = node['id'] in purchased
    if is_legacy:
        tier_ok = True
        eff_cost = effective_legacy_cost(node)
    else:
        effective_req = max(1, node.get('tier', 1) - gs.legacy_tier_offset)
        tier_ok = effective_req <= tier_cap
        eff_cost = node['cost']
    prereqs_met = all(p in purchased for p in node.get('prereqs', []))
    affordable = currency >= eff_cost

    y = body.y

    # Big name
    screen.blit(font_big.render(node['name'], True, W95_TEXT), (body.x, y))
    y += font_big.get_height() + 4

    # Status line
    if owned:
        status, scol = "OWNED", (0, 110, 0)
    elif not tier_ok:
        status, scol = f"LOCKED — needs Tier {node['tier']}", (140, 80, 0)
    elif not prereqs_met:
        status, scol = "LOCKED — prerequisites not met", (140, 80, 0)
    elif not affordable:
        status, scol = f"Cannot afford — need {eff_cost} {currency_name}", (140, 0, 0)
    else:
        status, scol = "AVAILABLE", (0, 100, 0)
    screen.blit(font_bold.render(status, True, scol), (body.x, y))
    y += font_bold.get_height() + 6

    # Sunken divider
    pygame.draw.line(screen, W95_SHADOW, (body.x, y), (body.right, y), 1)
    pygame.draw.line(screen, W95_LIGHT, (body.x, y + 1), (body.right, y + 1), 1)
    y += 8

    # Effect / description (word-wrapped)
    screen.blit(font_bold.render("Effect", True, W95_TEXT), (body.x, y))
    y += font_bold.get_height() + 2
    for ln in _wrap_text(node['desc'], font, body.w - 8):
        screen.blit(font.render(ln, True, (0, 0, 110)), (body.x + 8, y))
        y += font.get_height() + 1
    y += 6

    # Stat grid
    def kv(k, v, vcol=W95_TEXT):
        nonlocal y
        screen.blit(font.render(k, True, W95_TEXT), (body.x, y))
        screen.blit(font_bold.render(str(v), True, vcol), (body.x + 80, y))
        y += font.get_height() + 2

    if is_legacy and eff_cost != node['cost']:
        kv("Cost:", f"{eff_cost} {currency_name} (base {node['cost']})")
    else:
        kv("Cost:", f"{eff_cost} {currency_name}")
    if not is_legacy:
        tcol = W95_TEXT if tier_ok else (140, 80, 0)
        kv("Tier:", f"{node['tier']}   (cap: {tier_cap})", tcol)
    kv("Branch:", node['branch'].capitalize())
    y += 4

    # Prereqs
    screen.blit(font_bold.render("Prerequisites", True, W95_TEXT), (body.x, y))
    y += font_bold.get_height() + 2
    prereqs = node.get('prereqs', [])
    if not prereqs:
        screen.blit(font.render("(none)", True, W95_TEXT_DIM), (body.x + 8, y))
        y += font.get_height() + 1
    else:
        for pid in prereqs:
            pnode = node_db.get(pid)
            if not pnode:
                continue
            owned_p = pid in purchased
            mark = "[X]" if owned_p else "[  ]"
            pcol = (0, 110, 0) if owned_p else W95_TEXT
            screen.blit(font.render(f"{mark} {pnode['name']}", True, pcol), (body.x + 8, y))
            y += font.get_height() + 1

    # Buy button anchored to bottom of the panel
    can_buy = (not owned and tier_ok and prereqs_met and affordable)
    btn_rect = pygame.Rect(body.x, rect.bottom - 38, body.w, 30)
    action = 'buy_legacy' if is_legacy else 'buy_skill'
    buttons.append((btn_rect, action, node['id']))
    btn_label = "Already Owned" if owned else f"Buy  ({eff_cost} {currency_name})    [Enter]"
    draw_button(btn_rect, btn_label, enabled=can_buy, pressed=pressed_button == btn_rect,
                hovered=btn_rect.collidepoint(mx, my), font_obj=font_bold)


def _draw_inspector_repeatable(rect: pygame.Rect, mx: int, my: int, rep_id: str, body: pygame.Rect):
    """Inspector view for bounded-repeatable nodes — shows stacks owned, current and max-stack cost."""
    rep = REPEATABLE_BY_ID.get(rep_id)
    if not rep:
        screen.blit(font.render("(node missing)", True, W95_TEXT_DIM), (body.x, body.y + 6))
        return
    stacks = gs.purchased_repeatable.get(rep_id, 0)
    cur_cost = repeatable_cost(rep, stacks)
    last_cost = repeatable_cost(rep, rep['max_stacks'] - 1)
    tier_cap = get_unlocked_tier()
    tier_ok = rep.get('tier', 1) <= tier_cap
    maxed = stacks >= rep['max_stacks']
    affordable = gs.current_dp >= cur_cost

    y = body.y
    screen.blit(font_big.render(rep['name'], True, W95_TEXT), (body.x, y))
    y += font_big.get_height() + 4

    if maxed:
        status, scol = f"MAXED — {stacks}/{rep['max_stacks']} stacks owned", (0, 110, 0)
    elif not tier_ok:
        status, scol = f"LOCKED — needs Tier {rep['tier']}", (140, 80, 0)
    elif not affordable:
        status, scol = f"Cannot afford — need {cur_cost:,} DP", (140, 0, 0)
    else:
        status, scol = f"AVAILABLE — {stacks}/{rep['max_stacks']} owned", (0, 100, 0)
    screen.blit(font_bold.render(status, True, scol), (body.x, y))
    y += font_bold.get_height() + 6

    pygame.draw.line(screen, W95_SHADOW, (body.x, y), (body.right, y), 1)
    pygame.draw.line(screen, W95_LIGHT, (body.x, y + 1), (body.right, y + 1), 1)
    y += 8

    screen.blit(font_bold.render("Effect (per stack)", True, W95_TEXT), (body.x, y))
    y += font_bold.get_height() + 2
    for ln in _wrap_text(rep['desc'], font, body.w - 8):
        screen.blit(font.render(ln, True, (0, 0, 110)), (body.x + 8, y))
        y += font.get_height() + 1
    y += 6

    def kv(k, v, vcol=W95_TEXT):
        nonlocal y
        screen.blit(font.render(k, True, W95_TEXT), (body.x, y))
        screen.blit(font_bold.render(str(v), True, vcol), (body.x + 130, y))
        y += font.get_height() + 2

    kv("Stacks:", f"{stacks} / {rep['max_stacks']}")
    kv("Next cost:", f"{cur_cost:,} DP" if not maxed else "—")
    kv("Final cost:", f"{last_cost:,} DP" if not maxed else "owned")
    kv("Cost growth:", f"×{rep['cost_growth']:.2f} / stack")
    kv("Tier:", f"{rep['tier']}   (cap: {tier_cap})",
       W95_TEXT if tier_ok else (140, 80, 0))
    kv("Branch:", rep['branch'].capitalize())

    # Buy button — repeatables use 'buy_skill' too; the handler dispatches by ID lookup
    can_buy = (not maxed and tier_ok and affordable)
    btn_rect = pygame.Rect(body.x, rect.bottom - 38, body.w, 30)
    buttons.append((btn_rect, 'buy_skill', rep_id))
    if maxed:
        btn_label = "Fully Owned"
    else:
        btn_label = f"Buy stack #{stacks + 1}  ({cur_cost:,} DP)    [Enter]"
    draw_button(btn_rect, btn_label, enabled=can_buy, pressed=pressed_button == btn_rect,
                hovered=btn_rect.collidepoint(mx, my), font_obj=font_bold)


def draw_hub():
    draw_desktop()
    # Big "desktop" window holding the hub
    win = pygame.Rect(8, 8, WINDOW_WIDTH - 16, WINDOW_HEIGHT - TASKBAR_H - 16)
    client = draw_window(win, "Defragmenter Hub - Skill Tree")

    mx, my = pygame.mouse.get_pos()

    # Resource bar (sunken panel)
    res = pygame.Rect(client.x + 6, client.y + 6, client.w - 12, 24)
    draw_panel(res, raised=False)
    tier = get_unlocked_tier()
    line1 = (f"DP: {gs.current_dp}   LP: {gs.unspent_lp}   Prestige: #{gs.prestige_count}   "
             f"Highest: {gs.highest_disk_cleared or '—'}   Lifetime cleaned: {gs.total_lifetime_cleaned:,}   "
             f"Shatters: {gs.shatter_count_lifetime:,}   Tiers unlocked: 1–{tier}   Slot: {active_slot}")
    screen.blit(font.render(line1, True, W95_TEXT), (res.x + 8, res.y + 4))

    # Top-right action buttons inside the hub
    menu_btn = pygame.Rect(client.right - 116, client.y + 6, 110, 24)
    buttons.append((menu_btn, 'back_to_menu', None))
    draw_button(menu_btn, "Main Menu", True, pressed_button == menu_btn, menu_btn.collidepoint(mx, my))

    # Prestige... button — only entry point to the legacy/prestige UI. The whole interface
    # stays hidden during normal gameplay; player must deliberately open it. Always enabled
    # so first-time players can peek at what prestige offers; the Confirm button inside is
    # what actually gates the reset.
    prestige_btn = pygame.Rect(menu_btn.x - 158, client.y + 6, 150, 24)
    buttons.append((prestige_btn, 'open_prestige', None))
    draw_button(prestige_btn, "Prestige...", True,
                pressed_button == prestige_btn, prestige_btn.collidepoint(mx, my))

    # Skill tree panel (no tabs anymore — the HUB only shows the per-life Skill Tree).
    panel = pygame.Rect(client.x + 6, res.bottom + 6, client.w - 12, 410)
    draw_panel(panel, raised=False)
    # Section header
    hdr = pygame.Rect(panel.x + 2, panel.y + 2, panel.w - 4, 18)
    pygame.draw.rect(screen, W95_FACE_DIM, hdr)
    pygame.draw.line(screen, W95_SHADOW, (hdr.x, hdr.bottom - 1), (hdr.right, hdr.bottom - 1), 1)
    screen.blit(font_bold.render("Skill Tree  —  spend DP on per-life upgrades", True, W95_TEXT),
                (hdr.x + 6, hdr.y + 2))

    # Auto-buy toolbar
    toolbar = pygame.Rect(panel.x + 2, hdr.bottom, panel.w - 4, 28)
    pygame.draw.rect(screen, W95_FACE, toolbar)
    b1 = pygame.Rect(toolbar.x + 6, toolbar.y + 3, 168, toolbar.h - 6)
    b2 = pygame.Rect(b1.right + 6, toolbar.y + 3, 184, toolbar.h - 6)
    buttons.append((b1, 'auto_buy_skill_one', None))
    buttons.append((b2, 'auto_buy_skill_all', None))
    draw_button(b1, "Auto-Buy Cheapest", True, pressed_button == b1, b1.collidepoint(mx, my))
    draw_button(b2, "Auto-Buy All Affordable", True, pressed_button == b2, b2.collidepoint(mx, my))
    tip = "Greedy: cheapest available first, respecting tier + prereqs + DP."
    screen.blit(font_tiny.render(tip, True, W95_TEXT_DIM),
                (b2.right + 12, toolbar.y + (toolbar.h - 12) // 2))

    tree_panel = pygame.Rect(panel.x, toolbar.bottom, panel.w, panel.bottom - toolbar.bottom)
    draw_skill_tree(tree_panel, mx, my)

    # Bottom: disk select
    ds = pygame.Rect(client.x + 6, panel.bottom + 6, client.w - 12, client.bottom - panel.bottom - 12)
    draw_panel(ds, raised=False)
    draw_disk_select(ds, mx, my)


def draw_skill_tree(panel: pygame.Rect, mx: int, my: int):
    """Split layout: tree on the left, properties inspector on the right."""
    global tree_scroll_skill
    tree_w = int(panel.w * 0.56)
    tree_rect = pygame.Rect(panel.x + 4, panel.y + 4, tree_w, panel.h - 8)
    insp_rect = pygame.Rect(tree_rect.right + 6, panel.y + 4,
                            panel.w - tree_w - 14, panel.h - 8)

    rows = build_skill_tree_rows()
    tree_scroll_skill = draw_tree_pane(tree_rect, rows, tree_scroll_skill,
                                        tree_selected_skill_id, 'select_skill')
    draw_inspector(insp_rect, mx, my, tree_selected_skill_id, is_legacy=False)


def draw_prestige_screen():
    """Full-screen Prestige interface — only entered via the explicit 'Prestige...' button on HUB.
    Shows the legacy tree on the left, inspector on the right, plus Cancel and Confirm Prestige buttons."""
    global tree_scroll_legacy
    draw_desktop()
    win = pygame.Rect(40, 40, WINDOW_WIDTH - 80, WINDOW_HEIGHT - TASKBAR_H - 80)
    client = draw_window(win, "Prestige - Apply Legacy Upgrades and Reset Life")

    mx, my = pygame.mouse.get_pos()

    # Resource / instructions strip
    res = pygame.Rect(client.x + 6, client.y + 6, client.w - 12, 38)
    draw_panel(res, raised=False)
    line1 = (f"Unspent LP: {gs.unspent_lp}    "
             f"Owned legacies: {len(gs.purchased_legacy)}/{len(LEGACY_NODES)}    "
             f"Prestige count: #{gs.prestige_count}")
    line2 = "Buy permanent upgrades below, then Confirm Prestige to reset this life and activate them. Cancel returns without resetting."
    screen.blit(font_bold.render(line1, True, W95_TEXT), (res.x + 8, res.y + 4))
    screen.blit(font.render(line2, True, W95_TEXT_DIM), (res.x + 8, res.y + 20))

    # Auto-buy toolbar (same pattern as HUB)
    toolbar = pygame.Rect(client.x + 6, res.bottom + 4, client.w - 12, 28)
    pygame.draw.rect(screen, W95_FACE, toolbar)
    draw_bevel(toolbar, raised=True, outer=False)
    b1 = pygame.Rect(toolbar.x + 6, toolbar.y + 3, 168, toolbar.h - 6)
    b2 = pygame.Rect(b1.right + 6, toolbar.y + 3, 184, toolbar.h - 6)
    buttons.append((b1, 'auto_buy_legacy_one', None))
    buttons.append((b2, 'auto_buy_legacy_all', None))
    draw_button(b1, "Auto-Buy Cheapest", True, pressed_button == b1, b1.collidepoint(mx, my))
    draw_button(b2, "Auto-Buy All Affordable", True, pressed_button == b2, b2.collidepoint(mx, my))
    screen.blit(font_tiny.render("Greedy: cheapest legacy first, respecting LP + prereqs.", True, W95_TEXT_DIM),
                (b2.right + 12, toolbar.y + (toolbar.h - 12) // 2))

    # Tree + inspector panel
    btn_band_h = 44
    panel = pygame.Rect(client.x + 6, toolbar.bottom + 4, client.w - 12,
                        client.bottom - toolbar.bottom - 4 - btn_band_h)
    tree_w = int(panel.w * 0.56)
    tree_rect = pygame.Rect(panel.x, panel.y, tree_w, panel.h)
    insp_rect = pygame.Rect(tree_rect.right + 6, panel.y,
                            panel.w - tree_w - 6, panel.h)

    rows = build_legacy_tree_rows()
    tree_scroll_legacy = draw_tree_pane(tree_rect, rows, tree_scroll_legacy,
                                         tree_selected_legacy_id, 'select_legacy')
    draw_inspector(insp_rect, mx, my, tree_selected_legacy_id, is_legacy=True)

    # Bottom button band
    by = panel.bottom + 6
    cancel_btn = pygame.Rect(client.x + 6, by, 220, btn_band_h - 14)
    confirm_btn = pygame.Rect(client.right - 6 - 460, by, 460, btn_band_h - 14)

    can_confirm = (gs.prestige_count == 0) \
                  or (gs.total_lifetime_cleaned >= gs.prestige_lifetime_baseline + 100) \
                  or (len(gs.purchased_legacy) > 0)

    buttons.append((cancel_btn, 'cancel_prestige', None))
    buttons.append((confirm_btn, 'confirm_prestige', None))
    draw_button(cancel_btn, "Cancel  (Esc)", True,
                pressed_button == cancel_btn, cancel_btn.collidepoint(mx, my))
    draw_button(confirm_btn, "Confirm Prestige  —  reset life, activate legacies",
                enabled=can_confirm, pressed=pressed_button == confirm_btn,
                hovered=confirm_btn.collidepoint(mx, my), font_obj=font_bold)


disk_scroll_x = 0
_disk_strip_rect = pygame.Rect(0, 0, 0, 0)  # remembered for scroll wheel hit-testing


def draw_disk_select(panel: pygame.Rect, mx: int, my: int):
    """Horizontally scrolling strip of unlocked disks. Frontier disk highlighted in green.
    Mouse wheel over the strip scrolls horizontally. Arrow buttons on both ends nudge by one card."""
    global disk_scroll_x, _disk_strip_rect

    screen.blit(font_bold.render("Drive Selection", True, W95_TEXT), (panel.x + 8, panel.y + 4))
    if gs.session_end_reason:
        col = (0, 90, 0) if 'OPTIMIZED' in gs.session_end_reason else (130, 0, 0)
        msg = font.render(f"Last run: {gs.session_end_reason}   +{gs.earned_dp} DP   +{gs.earned_lp} LP",
                          True, col)
        screen.blit(msg, (panel.x + 180, panel.y + 6))

    highest_order = get_highest_cleared_order()
    max_order = highest_order + 1
    frontier = None
    for dk, o in DISK_ORDER.items():
        if o == highest_order + 1:
            frontier = dk
            break
    if frontier is None:
        frontier = gs.highest_disk_cleared or 'C:'

    # Strip layout — arrows on the ends, cards in between
    arrow_w = 22
    strip_y = panel.y + 22
    strip_h = panel.h - 28
    left_arrow = pygame.Rect(panel.x + 4, strip_y, arrow_w, strip_h)
    right_arrow = pygame.Rect(panel.right - arrow_w - 4, strip_y, arrow_w, strip_h)
    strip = pygame.Rect(left_arrow.right + 2, strip_y,
                        right_arrow.x - left_arrow.right - 4, strip_h)
    _disk_strip_rect = strip  # for the event loop wheel hit-test

    card_w = 150
    card_gap = 8
    unlocked = [(dk, DISK_ORDER[dk]) for dk in DISK_ORDER if DISK_ORDER[dk] <= max_order]
    total_w = len(unlocked) * (card_w + card_gap)
    max_scroll = max(0, total_w - strip.w)
    disk_scroll_x = max(0, min(disk_scroll_x, max_scroll))

    # Arrow buttons
    buttons.append((left_arrow, 'disk_scroll_left', None))
    buttons.append((right_arrow, 'disk_scroll_right', None))
    draw_button(left_arrow, "<", disk_scroll_x > 0,
                pressed_button == left_arrow, left_arrow.collidepoint(mx, my), font_obj=font_bold)
    draw_button(right_arrow, ">", disk_scroll_x < max_scroll,
                pressed_button == right_arrow, right_arrow.collidepoint(mx, my), font_obj=font_bold)

    # Clip the card row
    prev_clip = screen.get_clip()
    screen.set_clip(strip)

    x = strip.x - disk_scroll_x
    for disk_key, order in unlocked:
        card = pygame.Rect(x, strip.y, card_w, strip.h)
        x += card_w + card_gap
        # Skip rendering if entirely off-screen (saves work for huge disk lists)
        if card.right < strip.x or card.x > strip.right:
            continue
        is_f = (disk_key == frontier)
        timer = int(get_disk_timer(disk_key))
        cap = DISKS[disk_key]['capacity_gb']
        hardness = DISKS[disk_key]['hardness']
        draw_panel(card, raised=True)
        if is_f:
            # Green inner frame for the frontier disk
            inner = card.inflate(-4, -4)
            pygame.draw.rect(screen, (40, 140, 40), inner, 2)
        title_col = (0, 100, 0) if is_f else W95_TEXT
        screen.blit(font_bold.render(f"Drive {disk_key}", True, title_col),
                    (card.x + 8, card.y + 6))
        screen.blit(font_tiny.render(format_capacity(cap), True, W95_TEXT),
                    (card.x + 8, card.y + 26))
        # Hardness — show compact for huge values
        if hardness < 1000:
            h_str = f"hardness x{hardness:.1f}"
        elif hardness < 1e6:
            h_str = f"hardness x{hardness/1000:.1f}k"
        else:
            h_str = f"hardness x{hardness/1e6:.1f}M"
        screen.blit(font_tiny.render(h_str, True, W95_TEXT), (card.x + 8, card.y + 40))
        screen.blit(font_tiny.render(f"Timer: {timer}s", True, W95_TEXT),
                    (card.x + 8, card.y + 54))
        if is_f:
            screen.blit(font_tiny.render("> FRONTIER", True, (0, 100, 0)),
                        (card.x + 8, card.y + 68))
        else:
            screen.blit(font_tiny.render("(replay)", True, W95_TEXT_DIM),
                        (card.x + 8, card.y + 68))
        btn = pygame.Rect(card.x + 6, card.bottom - 22, card.w - 12, 18)
        buttons.append((btn, 'start_disk', disk_key))
        draw_button(btn, "Start Defrag", True, False, btn.collidepoint(mx, my), font_obj=font_tiny)

    screen.set_clip(prev_clip)

    # Faint count indicator (e.g. "5 / 24 drives unlocked")
    count_str = f"{len(unlocked)} / {len(DISK_LETTERS)} drives unlocked"
    surf = font_tiny.render(count_str, True, W95_TEXT_DIM)
    screen.blit(surf, (panel.right - surf.get_width() - 8, panel.y + 6))


# ============================================================================
# DRAW: PLAYING (the actual defrag window)
# ============================================================================

def draw_playing():
    draw_desktop()
    # Defrag window — same footprint as the hub so the transition between screens is seamless.
    win = pygame.Rect(8, 8, WINDOW_WIDTH - 16, WINDOW_HEIGHT - TASKBAR_H - 16)
    client = draw_window(win, f"Defragmenting Drive {gs.current_disk}")

    # Grid area
    grid_rect = pygame.Rect(client.x + 8, client.y + 8, client.w - 16, client.h - 110)
    draw_defrag_grid(grid_rect)

    # Status / progress band
    sb = pygame.Rect(client.x + 8, grid_rect.bottom + 6, client.w - 16, 18)
    pygame.draw.rect(screen, W95_FACE, sb)
    pct = 100.0 - gs.fragmentation
    if gs.session_cleaned == 0 and gs.current_autoclick <= 0 and gs.current_A <= 0:
        # First-time prompt: nothing has happened yet, no auto-anything — tell them to click
        msg = f">>> CLICK ANYWHERE ON THE GRID (or press SPACE) TO DEFRAGMENT <<<   {pct:.1f}% complete"
        screen.blit(font_bold.render(msg, True, (160, 0, 0)), (sb.x, sb.y))
    else:
        msg = (f"Defragmenting drive {gs.current_disk}...  "
               f"{pct:.1f}% complete   "
               f"clusters cleaned this session: {gs.session_cleaned}   "
               f"shatters: {gs.session_shatter_events}")
        screen.blit(font.render(msg, True, W95_TEXT), (sb.x, sb.y))

    # Progress bar — clean fraction
    pb = pygame.Rect(client.x + 8, sb.bottom + 4, client.w - 16, 14)
    draw_progress_bar(pb, pct / 100.0)

    # Bottom button row + readouts
    by = pb.bottom + 8
    mx, my = pygame.mouse.get_pos()
    bx = client.x + 8
    # Stop -> return to hub
    stop = pygame.Rect(bx, by, 88, 26)
    buttons.append((stop, 'stop_session', None))
    draw_button(stop, "Stop", True, pressed_button == stop, stop.collidepoint(mx, my))
    bx += 96
    pause = pygame.Rect(bx, by, 88, 26)
    buttons.append((pause, 'pause_session', None))
    draw_button(pause, "Resume (P)" if is_paused else "Pause (P)", True,
                pressed_button == pause, pause.collidepoint(mx, my))
    bx += 96
    legend = pygame.Rect(bx, by, 88, 26)
    buttons.append((legend, 'show_legend', None))
    draw_button(legend, "Legend (L)", True, pressed_button == legend, legend.collidepoint(mx, my))
    bx += 96
    hide = pygame.Rect(bx, by, 110, 26)
    buttons.append((hide, 'toggle_details', None))
    draw_button(hide, "Show Details" if hide_details else "Hide Details", True,
                pressed_button == hide, hide.collidepoint(mx, my))

    # Right-side stat readout (suppressed if Hide Details is active)
    now = pygame.time.get_ticks() / 1000.0
    real_cps = current_real_cps(now)
    if not hide_details:
        rate_now = (real_cps + gs.current_autoclick) * gs.current_M * gs.current_E + gs.current_A * gs.current_E
        re_r = DISKS[gs.current_disk]['write_intensity'] * gs.legacy_write_intensity_mult * (1.0 - gs.current_FR)
        stats = (f"M:{gs.current_M:.1f}  R cap:{gs.current_R:.2f}  Auto-CPS:{gs.current_autoclick:.2f}  "
                 f"A:{gs.current_A:.1f}  E:{gs.current_E:.2f}  FR:{gs.current_FR*100:.0f}%  "
                 f"|  CPS now:{real_cps:.1f}  Net:{rate_now:.0f}/s  Re-frag:{re_r:.1f}/s  "
                 f"|  Time {int(gs.time_left):3d}s")
        stats_surf = font_tiny.render(stats, True, W95_TEXT)
        screen.blit(stats_surf, (client.x + 8, by + 32))

        # CPS cap warning — inline at the right end of the stats line, only while recently capped
        if now - gs.rate_capped_recent < 0.6:
            cap_msg = font_tiny.render("  ⚠ CPS CAPPED — buy more Rate nodes", True, (180, 0, 0))
            screen.blit(cap_msg, (client.x + 8 + stats_surf.get_width(), by + 32))

    # End-state text overlays intentionally removed — the result message is now shown
    # only inside the end-of-session dialog, never floating over the grid. During the
    # 1.6 s celebration the grid simply renders fully clean (all cells cyan) as the
    # visual payoff, then the dialog pops with the formal result.

    # PAUSE overlay — dim the grid area + show centered banner. Drawn AFTER end-state overlays
    # so pause is always the topmost session-level indicator.
    if is_paused:
        # Translucent dim over the grid
        dim = pygame.Surface((grid_rect.w, grid_rect.h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
        screen.blit(dim, (grid_rect.x, grid_rect.y))
        # Banner — Win95 raised panel with PAUSED text
        bw, bh = 360, 80
        bx_p = grid_rect.x + (grid_rect.w - bw) // 2
        by_p = grid_rect.y + (grid_rect.h - bh) // 2
        banner = pygame.Rect(bx_p, by_p, bw, bh)
        draw_panel(banner, raised=True)
        title = font_huge.render("PAUSED", True, W95_TITLE_ACTIVE)
        screen.blit(title, (banner.x + (bw - title.get_width()) // 2, banner.y + 10))
        sub = font.render("Press P or click Resume to continue", True, W95_TEXT_DIM)
        screen.blit(sub, (banner.x + (bw - sub.get_width()) // 2, banner.y + 50))

    # LEGEND dialog — drawn last so it sits on top of everything else.
    if show_legend:
        draw_legend_dialog(mx, my)

    # END-OF-SESSION dialog — appears after end_session, must be acknowledged.
    # Drawn even on top of the legend (shouldn't ever happen but defensive).
    if show_end_dialog:
        draw_end_session_dialog(mx, my)


def draw_end_session_dialog(mx: int, my: int):
    """Win95 modal shown after end_session — player must click Continue (or press Enter/Esc)
    before returning to the hub. Shows the result, disk, DP/LP earned and session stats."""
    w, h = 460, 270
    win = pygame.Rect((WINDOW_WIDTH - w) // 2, (WINDOW_HEIGHT - h) // 2 - 30, w, h)
    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 110))
    screen.blit(overlay, (0, 0))

    success = 'OPTIMIZED' in gs.session_end_reason
    title_text = "Drive Optimized" if success else "Session Timed Out"
    client = draw_window(win, title_text, show_min=False, show_close=False)

    y = client.y + 14
    # Big result banner
    if success:
        big = font_huge.render("DRIVE OPTIMIZED!", True, (0, 130, 0))
    else:
        big = font_huge.render("SESSION TIMED OUT", True, (160, 30, 30))
    screen.blit(big, (client.x + (client.w - big.get_width()) // 2, y))
    y += big.get_height() + 12

    # Subtitle: which drive
    sub = font_bold.render(f"Drive {gs.current_disk}", True, W95_TEXT)
    screen.blit(sub, (client.x + (client.w - sub.get_width()) // 2, y))
    y += sub.get_height() + 10

    # Sunken divider
    pygame.draw.line(screen, W95_SHADOW, (client.x + 20, y), (client.right - 20, y), 1)
    pygame.draw.line(screen, W95_LIGHT,  (client.x + 20, y + 1), (client.right - 20, y + 1), 1)
    y += 10

    # Reward lines
    def stat_line(label: str, value: str, val_col=W95_TEXT):
        nonlocal y
        screen.blit(font.render(label, True, W95_TEXT), (client.x + 36, y))
        vs = font_bold.render(value, True, val_col)
        screen.blit(vs, (client.right - 36 - vs.get_width(), y))
        y += font.get_height() + 4

    stat_line("Earned DP:", f"+{gs.earned_dp:,}", (0, 80, 0) if gs.earned_dp > 0 else W95_TEXT_DIM)
    if gs.earned_lp > 0:
        stat_line("Earned LP:", f"+{gs.earned_lp:,}", (80, 60, 0))
    stat_line("Clusters cleaned:", f"{gs.session_cleaned:,}")
    if gs.session_shatter_events > 0:
        stat_line("Shatter events:", f"{gs.session_shatter_events:,}")

    # Continue button — anchored to bottom, default focus
    btn = pygame.Rect(client.x + (client.w - 160) // 2, client.bottom - 38, 160, 28)
    buttons.append((btn, 'continue_from_session', None))
    draw_button(btn, "Continue  [Enter]", True, pressed_button == btn,
                btn.collidepoint(mx, my), font_obj=font_bold)


def draw_legend_dialog(mx: int, my: int):
    """Win95 modal dialog: cell color/type legend + status icon meanings + key mechanics."""
    w, h = 600, 580
    win = pygame.Rect((WINDOW_WIDTH - w) // 2, (WINDOW_HEIGHT - h) // 2 - 20, w, h)
    # Drop shadow effect: dim everything underneath very subtly
    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 80))
    screen.blit(overlay, (0, 0))

    client = draw_window(win, "Defrag Legend")

    y = client.y + 12
    screen.blit(font_bold.render("Cell colors (in the defrag grid):", True, W95_TEXT), (client.x + 12, y))
    y += 22

    # Legend rows: swatch + label + description. Color names match the VGA-16 palette
    # used on the grid (true Win95/98 defrag visual style).
    legend_rows = [
        (DEFRAG_GOOD,  "Cyan",    "Optimized cluster — contiguous good data"),
        (FRAG_TEMP,    "Yellow",  "Temp file — cheapest to clean (0.6× cost)"),
        (FRAG_DOC,     "Green",   "Document — moderate cost (1.0×)"),
        (FRAG_MEDIA,   "Magenta", "Media file — expensive (1.8×)"),
        (FRAG_SYS,     "Red",     "System file — costliest (2.5×) — shatters on clean"),
        (HIGHLIGHT_BORDER, "Grey outline", "Cell just changed state — fades after a moment"),
    ]
    for color, name, desc in legend_rows:
        swatch = pygame.Rect(client.x + 18, y + 2, 18, 14)
        pygame.draw.rect(screen, color, swatch)
        pygame.draw.rect(screen, W95_DARK, swatch, 1)
        screen.blit(font_bold.render(name, True, W95_TEXT), (swatch.right + 8, y))
        screen.blit(font.render(desc, True, W95_TEXT), (swatch.right + 90, y))
        y += 22

    y += 6
    pygame.draw.line(screen, W95_SHADOW, (client.x + 8, y), (client.right - 8, y), 1)
    pygame.draw.line(screen, W95_LIGHT,  (client.x + 8, y + 1), (client.right - 8, y + 1), 1)
    y += 8

    screen.blit(font_bold.render("Status icons in the skill / prestige tree:", True, W95_TEXT), (client.x + 12, y))
    y += 22
    status_rows = [
        ((40, 160, 40),    "Green",   "Owned (fully maxed for repeatables)"),
        ((230, 200, 50),   "Yellow",  "Available to buy now"),
        ((170, 170, 170),  "Gray",    "Tier + prereqs met, but you can't afford it yet"),
        ((170, 60, 60),    "Red",     "Locked — tier requirement or prerequisite missing"),
    ]
    for color, name, desc in status_rows:
        swatch = pygame.Rect(client.x + 18, y + 2, 14, 14)
        pygame.draw.rect(screen, color, swatch)
        pygame.draw.rect(screen, W95_DARK, swatch, 1)
        screen.blit(font_bold.render(name, True, W95_TEXT), (swatch.right + 8, y))
        screen.blit(font.render(desc, True, W95_TEXT), (swatch.right + 80, y))
        y += 22

    y += 6
    pygame.draw.line(screen, W95_SHADOW, (client.x + 8, y), (client.right - 8, y), 1)
    pygame.draw.line(screen, W95_LIGHT,  (client.x + 8, y + 1), (client.right - 8, y + 1), 1)
    y += 8

    screen.blit(font_bold.render("Mechanics:", True, W95_TEXT), (client.x + 12, y))
    y += 22
    mechanic_lines = [
        "Shatter — Cleaning a heavy file spawns lighter fragments (sys → media → doc → temp).",
        "Cascade — On later disks, those spawned fragments may shatter further (chaos).",
        "Refrag — While Auto is active, writes re-fragment cells over time; FR reduces this.",
        "Click cap (R) — Real clicks above R/sec are ignored; auto-clickers bypass the cap.",
        "Prestige — Resets per-life skills + DP, keeps disk unlocks and legacy nodes.",
    ]
    for ln in mechanic_lines:
        for piece in _wrap_text(ln, font_tiny, client.w - 28):
            screen.blit(font_tiny.render(piece, True, W95_TEXT), (client.x + 18, y))
            y += font_tiny.get_height() + 1
        y += 3

    # Close button (anchored bottom)
    close_btn = pygame.Rect(client.x + (client.w - 110) // 2, client.bottom - 36, 110, 26)
    buttons.append((close_btn, 'hide_legend', None))
    draw_button(close_btn, "Close (L)", True, pressed_button == close_btn,
                close_btn.collidepoint(mx, my))


# ============================================================================
# EVENT DISPATCH
# ============================================================================

def handle_button(action: str, payload, mx: int, my: int):
    global active_slot, game_state, tree_selected_skill_id, tree_selected_legacy_id
    global is_paused, show_legend, show_end_dialog, hide_details, disk_scroll_x

    if action == 'noop':
        return

    # While the end-of-session modal is up, only Continue is accepted. This stops
    # underlying buttons (Stop/Pause/Legend) from being clicked through the dialog.
    if show_end_dialog and action != 'continue_from_session':
        return

    if action == 'new_game':
        # Default to slot 1 unless 1 is empty
        for s in (1, 2, 3):
            if not slot_summary(s):
                active_slot = s
                break
        else:
            active_slot = 1
        reset_for_new_game()
        save_game(active_slot)
        set_state('HUB')

    elif action == 'load_menu':
        set_state('LOAD')

    elif action == 'settings':
        set_state('SETTINGS')

    elif action == 'quit':
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    elif action == 'back_title':
        set_state('TITLE')

    elif action == 'load_slot':
        slot = payload
        if load_game(slot):
            active_slot = slot
            set_state('HUB')

    elif action == 'delete_slot':
        delete_slot(payload)

    elif action == 'new_in_slot':
        active_slot = payload
        reset_for_new_game()
        save_game(active_slot)
        set_state('HUB')

    elif action == 'back_to_menu':
        save_game(active_slot)
        set_state('TITLE')

    elif action == 'open_prestige':
        # Player explicitly chose to access the prestige interface.
        set_state('PRESTIGE')

    elif action == 'cancel_prestige':
        # Return to HUB without performing prestige. Any legacy purchases made in
        # the dialog (current model: applied immediately on click) are kept; the player
        # still has to click Confirm Prestige to actually reset their life.
        set_state('HUB')

    elif action == 'toggle_tree':
        # payload is either a branch key string or a ('legacy', branch) / (branch, family) tuple
        if payload in tree_expanded:
            tree_expanded.discard(payload)
        else:
            tree_expanded.add(payload)

    elif action == 'select_skill':
        tree_selected_skill_id = payload

    elif action == 'select_legacy':
        tree_selected_legacy_id = payload

    elif action == 'buy_skill':
        # First try repeatables (same ID namespace from the player's perspective)
        rep = REPEATABLE_BY_ID.get(payload)
        if rep:
            stacks = gs.purchased_repeatable.get(payload, 0)
            if can_purchase_repeatable(rep, stacks, gs.current_dp, get_unlocked_tier()):
                gs.current_dp -= repeatable_cost(rep, stacks)
                gs.purchased_repeatable[payload] = stacks + 1
                recompute_stats()
                save_game(active_slot)
                # Keep selection on the same repeatable so Enter chains buys
                tree_selected_skill_id = payload
            return

        node = SKILL_BY_ID.get(payload)
        if node and can_purchase(node, gs.purchased_nodes, gs.current_dp, get_unlocked_tier()):
            gs.current_dp -= node['cost']
            gs.purchased_nodes.add(payload)
            if node['effect']['type'] == 'time':
                gs.extra_timer_secs += node['effect']['value']
            recompute_stats()
            save_game(active_slot)
            # Auto-advance selection to the next node in the same line so the player can
            # press Enter repeatedly to grind a line.
            fam = family_of(node)
            siblings = sorted(
                [n for n in SKILL_NODES if n['branch'] == node['branch'] and family_of(n) == fam],
                key=lambda n: (n['tier'], n['cost']))
            idx = next((i for i, n in enumerate(siblings) if n['id'] == payload), -1)
            if 0 <= idx and idx + 1 < len(siblings):
                tree_selected_skill_id = siblings[idx + 1]['id']

    elif action == 'auto_buy_skill_one':
        # Buy the single cheapest available item — considers BOTH skill nodes and repeatables
        tier_cap = get_unlocked_tier()
        candidates = []
        for n in SKILL_NODES:
            if can_purchase(n, gs.purchased_nodes, gs.current_dp, tier_cap):
                candidates.append(('skill', n, n['cost']))
        for r in REPEATABLE_NODES:
            stacks = gs.purchased_repeatable.get(r['id'], 0)
            if can_purchase_repeatable(r, stacks, gs.current_dp, tier_cap):
                candidates.append(('rep', r, repeatable_cost(r, stacks)))
        if candidates:
            candidates.sort(key=lambda x: (x[2], x[1]['id']))
            kind, item, cost = candidates[0]
            if kind == 'skill':
                gs.current_dp -= cost
                gs.purchased_nodes.add(item['id'])
                if item['effect']['type'] == 'time':
                    gs.extra_timer_secs += item['effect']['value']
            else:
                gs.current_dp -= cost
                gs.purchased_repeatable[item['id']] = gs.purchased_repeatable.get(item['id'], 0) + 1
            tree_selected_skill_id = item['id']
            recompute_stats()
            save_game(active_slot)

    elif action == 'auto_buy_skill_all':
        # Greedy cheapest-first across skill nodes AND repeatables
        bought = 0
        while bought < 2000:
            tier_cap = get_unlocked_tier()
            candidates = []
            for n in SKILL_NODES:
                if can_purchase(n, gs.purchased_nodes, gs.current_dp, tier_cap):
                    candidates.append(('skill', n, n['cost']))
            for r in REPEATABLE_NODES:
                stacks = gs.purchased_repeatable.get(r['id'], 0)
                if can_purchase_repeatable(r, stacks, gs.current_dp, tier_cap):
                    candidates.append(('rep', r, repeatable_cost(r, stacks)))
            if not candidates:
                break
            candidates.sort(key=lambda x: (x[2], x[1]['id']))
            kind, item, cost = candidates[0]
            if kind == 'skill':
                gs.current_dp -= cost
                gs.purchased_nodes.add(item['id'])
                if item['effect']['type'] == 'time':
                    gs.extra_timer_secs += item['effect']['value']
            else:
                gs.current_dp -= cost
                gs.purchased_repeatable[item['id']] = gs.purchased_repeatable.get(item['id'], 0) + 1
            tree_selected_skill_id = item['id']
            bought += 1
        if bought:
            recompute_stats()
            save_game(active_slot)

    elif action == 'buy_legacy':
        node = LEGACY_BY_ID.get(payload)
        if not node:
            return
        # Architect: future legacy costs are multiplied by legacy_lp_cost_mult (e.g. 0.90)
        eff_cost = max(1, int(node['cost'] * gs.legacy_lp_cost_mult))
        # Milestone gating — node unavailable until prestige_count threshold met
        min_pc = node.get('min_prestige_count', 0)
        if (payload not in gs.purchased_legacy and
                all(p in gs.purchased_legacy for p in node.get('prereqs', [])) and
                gs.unspent_lp >= eff_cost and
                gs.prestige_count >= min_pc):
            gs.unspent_lp -= eff_cost
            gs.purchased_legacy.add(payload)
            recompute_legacy_bonuses()
            recompute_stats()
            save_game(active_slot)
            # Auto-advance to the next legacy in this branch
            branch = node['branch']
            sibs = [n for n in LEGACY_NODES if n['branch'] == branch]
            idx = next((i for i, n in enumerate(sibs) if n['id'] == payload), -1)
            if 0 <= idx and idx + 1 < len(sibs):
                tree_selected_legacy_id = sibs[idx + 1]['id']

    elif action == 'auto_buy_legacy_one':
        def _eff_cost(n):
            return max(1, int(n['cost'] * gs.legacy_lp_cost_mult))
        def _legacy_buyable(n):
            return (n['id'] not in gs.purchased_legacy
                    and all(p in gs.purchased_legacy for p in n.get('prereqs', []))
                    and gs.prestige_count >= n.get('min_prestige_count', 0)
                    and gs.unspent_lp >= _eff_cost(n))
        cands = [n for n in LEGACY_NODES if _legacy_buyable(n)]
        if cands:
            cands.sort(key=lambda n: (_eff_cost(n), n['name']))
            n = cands[0]
            gs.unspent_lp -= _eff_cost(n)
            gs.purchased_legacy.add(n['id'])
            tree_selected_legacy_id = n['id']
            recompute_legacy_bonuses()
            recompute_stats()
            save_game(active_slot)

    elif action == 'auto_buy_legacy_all':
        def _eff_cost(n):
            return max(1, int(n['cost'] * gs.legacy_lp_cost_mult))
        def _legacy_buyable(n):
            return (n['id'] not in gs.purchased_legacy
                    and all(p in gs.purchased_legacy for p in n.get('prereqs', []))
                    and gs.prestige_count >= n.get('min_prestige_count', 0)
                    and gs.unspent_lp >= _eff_cost(n))
        bought = 0
        while bought < 100:
            cands = [n for n in LEGACY_NODES if _legacy_buyable(n)]
            if not cands:
                break
            cands.sort(key=lambda n: (_eff_cost(n), n['name']))
            n = cands[0]
            gs.unspent_lp -= _eff_cost(n)
            gs.purchased_legacy.add(n['id'])
            tree_selected_legacy_id = n['id']
            bought += 1
        if bought:
            recompute_legacy_bonuses()
            recompute_stats()
            save_game(active_slot)

    elif action == 'confirm_prestige':
        perform_prestige()

    elif action == 'start_disk':
        if payload in DISKS:
            d_order = DISK_ORDER.get(payload, 999)
            if d_order <= get_highest_cleared_order() + 1:
                start_session(payload)

    elif action == 'disk_scroll_left':
        disk_scroll_x = max(0, disk_scroll_x - 158)

    elif action == 'disk_scroll_right':
        # the per-frame clamp in draw_disk_select handles the upper bound
        disk_scroll_x = disk_scroll_x + 158

    elif action == 'stop_session':
        # If a win is already mid-celebration, treat Stop/Back as "skip the celebration" — not as a failure.
        if gs.victory_celebration_until > 0:
            gs.victory_celebration_until = 0.0
            end_session(success=True)
        else:
            end_session(success=False)

    elif action == 'pause_session':
        is_paused = not is_paused

    elif action == 'show_legend':
        show_legend = not show_legend

    elif action == 'hide_legend':
        show_legend = False

    elif action == 'toggle_details':
        hide_details = not hide_details

    elif action == 'continue_from_session':
        # Dismiss end-of-session modal and transition to HUB
        show_end_dialog = False
        set_state('HUB')
        set_hub_view('skill')


# ============================================================================
# MAIN LOOP
# ============================================================================

def main():
    global pressed_button, active_slot, tree_scroll_skill, tree_scroll_legacy, disk_scroll_x
    global is_paused, show_legend, show_end_dialog, hide_details

    # Bootstrap defaults — autoload slot 1 if exists, else fresh
    if slot_summary(1):
        load_game(1)
        active_slot = 1
    else:
        reset_for_new_game()

    last_time = pygame.time.get_ticks() / 1000.0
    running = True

    while running:
        now = pygame.time.get_ticks() / 1000.0
        dt = now - last_time
        last_time = now
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                save_game(active_slot)
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if game_state == 'PLAYING':
                        if show_end_dialog:
                            # Dismiss end-of-session modal
                            handle_button('continue_from_session', None, mx, my)
                        elif gs.victory_celebration_until > 0:
                            gs.victory_celebration_until = 0.0
                            end_session(success=True)
                        else:
                            end_session(success=False)
                    elif game_state == 'PRESTIGE':
                        set_state('HUB')
                    elif game_state in ('LOAD', 'SETTINGS'):
                        set_state('TITLE')
                    elif game_state == 'HUB':
                        save_game(active_slot)
                        set_state('TITLE')
                    else:
                        save_game(active_slot)
                        running = False
                elif game_state == 'PLAYING':
                    # When end dialog is up, only Enter dismisses it; other keys ignored.
                    if show_end_dialog:
                        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            handle_button('continue_from_session', None, mx, my)
                    elif event.key == pygame.K_l:
                        show_legend = not show_legend
                    elif event.key == pygame.K_p:
                        is_paused = not is_paused
                    elif event.key == pygame.K_SPACE:
                        if not is_paused and not show_legend:
                            trigger_manual_sweep(now)
                    elif event.key == pygame.K_b:
                        if gs.victory_celebration_until > 0:
                            gs.victory_celebration_until = 0.0
                            end_session(success=True)
                        else:
                            end_session(success=False)
                elif game_state == 'HUB':
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        # Enter buys the selected skill node
                        if tree_selected_skill_id:
                            handle_button('buy_skill', tree_selected_skill_id, mx, my)
                elif game_state == 'PRESTIGE':
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        # Enter buys the selected legacy node
                        if tree_selected_legacy_id:
                            handle_button('buy_legacy', tree_selected_legacy_id, mx, my)

            elif event.type == pygame.MOUSEWHEEL:
                if game_state == 'HUB':
                    # Disk strip scroll if mouse is over the strip, else scroll the skill tree.
                    if _disk_strip_rect.collidepoint(mx, my):
                        disk_scroll_x = max(0, disk_scroll_x - event.y * 158)
                    else:
                        tree_scroll_skill = max(0, tree_scroll_skill - event.y * TREE_ROW_H * 2)
                elif game_state == 'PRESTIGE':
                    tree_scroll_legacy = max(0, tree_scroll_legacy - event.y * TREE_ROW_H * 2)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Track pressed button for visual; resolved on mouseup
                pressed_button = None
                for rect, action, payload in buttons:
                    if rect.collidepoint(mx, my):
                        pressed_button = rect
                        break
                # In PLAYING also handle click on grid (but not when paused, legend showing, or end-of-session dialog up).
                # The window rect here MUST stay in sync with draw_playing's `win`.
                if game_state == 'PLAYING' and not is_paused and not show_legend and not show_end_dialog:
                    win_rect = pygame.Rect(8, 8, WINDOW_WIDTH - 16, WINDOW_HEIGHT - TASKBAR_H - 16)
                    client = pygame.Rect(win_rect.x + WINDOW_BORDER,
                                         win_rect.y + WINDOW_BORDER + TITLEBAR_H + 1,
                                         win_rect.w - 2 * WINDOW_BORDER,
                                         win_rect.h - 2 * WINDOW_BORDER - TITLEBAR_H - 1)
                    grid_rect = pygame.Rect(client.x + 8, client.y + 8, client.w - 16, client.h - 110)
                    if cell_at_pixel(grid_rect, mx, my) is not None:
                        trigger_manual_sweep(now)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                # Fire action only if mouse-up on the same button
                fired = False
                for rect, action, payload in buttons:
                    if rect.collidepoint(mx, my) and rect == pressed_button:
                        handle_button(action, payload, mx, my)
                        fired = True
                        break
                pressed_button = None
                if fired:
                    buttons.clear()

        # Per-frame sim
        if game_state == 'PLAYING':
            session_active = (gs.time_left > 0
                              and gs.fragmentation > COMPLETION_FRAG_PERCENT
                              and gs.victory_celebration_until == 0.0
                              and not is_paused
                              and not show_end_dialog)

            # Sim ticks only while the session is still in play (paused = skipped)
            if session_active:
                gs.time_left -= dt
                update_continuous_progress(dt, now)
                apply_refragmentation(dt)

            # Win check — independent of the sim guard so clicks that clear the drive count.
            # Gated by `not is_paused and not show_end_dialog` so a paused or completed
            # session is truly frozen and doesn't re-fire end_session while the dialog is up.
            if not is_paused and not show_end_dialog:
                if gs.fragmentation <= COMPLETION_FRAG_PERCENT and gs.victory_celebration_until == 0.0:
                    gs.victory_celebration_until = now + 1.6
                    for row in gs.grid:
                        for cell in row:
                            if cell.state == 'fragmented':
                                cell.state = 'good'
                    update_fragmentation()
                elif gs.time_left <= 0 and gs.victory_celebration_until == 0.0:
                    end_session(success=False)
                elif gs.victory_celebration_until > 0 and now >= gs.victory_celebration_until:
                    gs.victory_celebration_until = 0.0
                    end_session(success=True)

        # Draw
        buttons.clear()
        if game_state == 'TITLE':
            draw_title_screen()
        elif game_state == 'MENU':
            draw_title_screen()
        elif game_state == 'LOAD':
            draw_load_screen()
        elif game_state == 'SETTINGS':
            draw_settings_screen()
        elif game_state == 'HUB':
            draw_hub()
            if gs.prestige_banner_until > now:
                msg = font_big.render("Prestige complete — legacies active. Stronger start!", True, (0, 100, 0))
                bx = (WINDOW_WIDTH - msg.get_width()) // 2
                by = WINDOW_HEIGHT - TASKBAR_H - 36
                pygame.draw.rect(screen, W95_FACE, (bx - 8, by - 4, msg.get_width() + 16, msg.get_height() + 8))
                draw_bevel(pygame.Rect(bx - 8, by - 4, msg.get_width() + 16, msg.get_height() + 8), raised=True)
                screen.blit(msg, (bx, by))
        elif game_state == 'PRESTIGE':
            draw_prestige_screen()
        elif game_state == 'PLAYING':
            draw_playing()

        draw_taskbar(game_state)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()

"""
DEFRAG.EXE balance simulator.

Drives the actual game logic (apply_power, recompute_stats, perform_prestige_pure)
in fast-forward under a synthetic-player model. Outputs metrics CSV and supports
parameter sweeps for tuning.

Usage:
    # Single baseline run, print to stdout:
    python tools/balance_sim.py
    python tools/balance_sim.py --verbose
    python tools/balance_sim.py --csv out.csv

    # Sweep mode (grid over a few parameters):
    python tools/balance_sim.py --sweep \\
        hardness_growth=1.30,1.35,1.40,1.45 \\
        prestige_mult=0.15,0.20,0.25,0.30
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from itertools import product
from pathlib import Path

# Make pygame headless before importing main
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

import main  # noqa: E402  (pygame inits at import time, hence the env vars above)


# ============================================================================
# SYNTHETIC PLAYER MODEL
# ============================================================================

BASE_PLAYER_CPS = 2.0       # peak engagement (no auto-clickers owned)
ENGAGEMENT_DECAY_AUTO_CPS = 25.0  # higher → player stays engaged longer


def synthetic_player_cps(auto_cps: float) -> float:
    """Average player's real CPS, decays as auto-clickers carry more work.

        auto=0  -> 2.0
        auto=10 -> 1.34
        auto=25 -> 0.74
        auto=50 -> 0.27
        auto=100+ -> ~0
    """
    return BASE_PLAYER_CPS * math.exp(-auto_cps / ENGAGEMENT_DECAY_AUTO_CPS)


# ============================================================================
# BALANCE CONFIG (what the sweep can vary)
# ============================================================================

class BalanceConfig:
    """All tunable values the sweep can vary. Each `apply` mutates main module
    state in-place so the rest of the sim just calls the normal functions."""
    def __init__(self,
                 hardness_growth: float = 1.45,
                 prestige_mult: float = 0.20,
                 rep_cost_growth_power: float = 1.40,
                 rep_cost_growth_botmult: float = 1.45,
                 rep_cost_growth_heatsink: float = 1.40,
                 rep_cost_growth_alloc: float = 1.50,
                 rep_max_stacks_power: int = 25,
                 rep_max_stacks_botmult: int = 22,
                 rep_max_stacks_heatsink: int = 28,
                 rep_max_stacks_alloc: int = 20,
                 dp_mult_global: float = 1.0,
                 cascade_scale: float = 1.0):
        self.hardness_growth = hardness_growth
        self.prestige_mult = prestige_mult
        self.rep_cost_growth = {
            'rep_power':     rep_cost_growth_power,
            'rep_botmult':   rep_cost_growth_botmult,
            'rep_heatsink':  rep_cost_growth_heatsink,
            'rep_alloc':     rep_cost_growth_alloc,
        }
        self.rep_max_stacks = {
            'rep_power':     rep_max_stacks_power,
            'rep_botmult':   rep_max_stacks_botmult,
            'rep_heatsink':  rep_max_stacks_heatsink,
            'rep_alloc':     rep_max_stacks_alloc,
        }
        self.dp_mult_global = dp_mult_global
        self.cascade_scale = cascade_scale

    def apply(self):
        """Push config values into the main module. Regenerates DISKS from scratch each
        call so compound mutations across configs don't leak."""
        # 1. Regenerate DISKS from main's generator, then overwrite tunable fields.
        fresh = main._generate_disks()
        for k, v in fresh.items():
            main.DISKS[k] = v
        # Override hardness (post-H growth rate) and cascade scale
        for i, letter in enumerate(main.DISK_LETTERS):
            order = i + 1
            disk = main.DISKS[letter + ':']
            if order > 6:
                disk['hardness'] = round(55.0 * (self.hardness_growth ** (order - 6)), 1)
            disk['cascade_chance'] = min(0.95, disk['cascade_chance'] * self.cascade_scale)

        # 2. Prestige global mult
        rate = self.prestige_mult
        main.prestige_global_mult = lambda r=rate: 1.0 + r * main.gs.prestige_count

        # 3. Repeatable node cost growth + max stacks
        for nid, growth in self.rep_cost_growth.items():
            node = main.REPEATABLE_BY_ID.get(nid)
            if node:
                node['cost_growth'] = growth
        for nid, mx in self.rep_max_stacks.items():
            node = main.REPEATABLE_BY_ID.get(nid)
            if node:
                node['max_stacks'] = mx

    def reset(self):
        """Restore default config values (to baseline)."""
        BalanceConfig().apply()


# ============================================================================
# SIMULATION CORE
# ============================================================================

def simulate_session(time_step: float = 1.0, max_session_time: float | None = None) -> dict:
    """Simulate one defrag session on gs.current_disk.

    Returns dict with: success (bool), sim_seconds (float), cleaned (int), shatters (int)."""
    if max_session_time is None:
        max_session_time = main.gs.time_left

    sim_t = 0.0
    last_real_click_t = -10.0
    initial_cleaned = main.gs.session_cleaned
    initial_shatters = main.gs.session_shatter_events

    while sim_t < max_session_time:
        # Win check (clicking is so coarse here that we may win mid-step)
        if main.gs.fragmentation <= main.COMPLETION_FRAG_PERCENT:
            return {
                'success': True, 'sim_seconds': sim_t,
                'cleaned': main.gs.session_cleaned - initial_cleaned,
                'shatters': main.gs.session_shatter_events - initial_shatters,
            }

        # Player real CPS (capped at R)
        real_cps = min(synthetic_player_cps(main.gs.current_autoclick), main.gs.current_R)

        # Power per click: M * E * click_multi * (1 + crit_chance) [crit doubles → +1 per crit avg]
        per_click = main.gs.current_M * main.gs.current_E * main.gs.current_click_multi
        per_click *= (1.0 + main.gs.current_crit_chance)
        # Click Echo: each accepted click has chance for ghost at 60%
        echo = main.gs.current_click_echo_chance * 0.60
        per_click_eff = per_click * (1.0 + echo)

        manual_power = real_cps * per_click_eff * time_step
        auto_power = main.gs.current_autoclick * per_click * time_step  # echo only on real clicks
        a_eff = main.gs.current_A
        # Idle A bonus when no real clicks recently
        idle_for = sim_t - last_real_click_t
        if real_cps < 0.1 and main.gs.current_A_idle > 0:
            a_eff += main.gs.current_A * main.gs.current_A_idle
        if main.gs.fragmentation < 25 and main.gs.current_A_low > 0:
            a_eff += main.gs.current_A * main.gs.current_A_low
        # Background Sweep
        if main.gs.current_background_sweep_active and idle_for >= 5.0:
            a_eff *= max(1.0, main.gs.current_R / main.BASE_R)
        a_power = a_eff * main.gs.current_E * time_step

        # M conditional bonuses scaled by total CPS
        m_cond = 0.0
        if main.gs.fragmentation > 55:
            m_cond += main.gs.current_M * main.gs.current_M_high
        if main.gs.fragmentation < 25:
            m_cond += main.gs.current_M * main.gs.current_M_low
        cond_power = 0.0
        if m_cond > 0:
            cond_power = m_cond * (real_cps + main.gs.current_autoclick) * main.gs.current_E * time_step

        total_power = manual_power + auto_power + a_power + cond_power
        if total_power > 0:
            main.apply_power(total_power)

        main.apply_refragmentation(time_step)

        if real_cps > 0.1:
            last_real_click_t = sim_t
        sim_t += time_step

    return {
        'success': main.gs.fragmentation <= main.COMPLETION_FRAG_PERCENT,
        'sim_seconds': sim_t,
        'cleaned': main.gs.session_cleaned - initial_cleaned,
        'shatters': main.gs.session_shatter_events - initial_shatters,
    }


def buy_skills_greedy() -> int:
    """Greedy cheapest from skill + repeatable trees until no purchase is affordable.
    Returns count of nodes bought."""
    n = 0
    while n < 2000:
        tier_cap = main.get_unlocked_tier()
        candidates = []
        for node in main.SKILL_NODES:
            if main.can_purchase(node, main.gs.purchased_nodes, main.gs.current_dp, tier_cap):
                candidates.append(('skill', node, node['cost']))
        for node in main.REPEATABLE_NODES:
            stacks = main.gs.purchased_repeatable.get(node['id'], 0)
            if main.can_purchase_repeatable(node, stacks, main.gs.current_dp, tier_cap):
                candidates.append(('rep', node, main.repeatable_cost(node, stacks)))
        if not candidates:
            break
        candidates.sort(key=lambda x: x[2])
        kind, node, cost = candidates[0]
        if kind == 'skill':
            main.gs.current_dp -= cost
            main.gs.purchased_nodes.add(node['id'])
            if node['effect']['type'] == 'time':
                main.gs.extra_timer_secs += node['effect']['value']
        else:
            main.gs.current_dp -= cost
            main.gs.purchased_repeatable[node['id']] = main.gs.purchased_repeatable.get(node['id'], 0) + 1
        main.recompute_stats()
        n += 1
    return n


def buy_legacies_greedy() -> int:
    """Greedy cheapest legacy buys until LP runs out."""
    n = 0
    while n < 100:
        cands = [node for node in main.LEGACY_NODES
                 if node['id'] not in main.gs.purchased_legacy
                 and all(p in main.gs.purchased_legacy for p in node.get('prereqs', []))
                 and main.gs.unspent_lp >= node['cost']]
        if not cands:
            break
        cands.sort(key=lambda x: x['cost'])
        node = cands[0]
        main.gs.unspent_lp -= node['cost']
        main.gs.purchased_legacy.add(node['id'])
        n += 1
    if n:
        main.recompute_legacy_bonuses()
        main.recompute_stats()
    return n


def run_full_simulation(real_time_limit: float = 7200.0,
                        verbose: bool = False,
                        consecutive_fail_cap: int = 8) -> list[dict]:
    """Play from new game to Z: (or time-out). Returns per-session record list.

    Strategy:
      * Pick frontier disk
      * Buy everything affordable (skill + repeatable + legacy) before the attempt
      * Play session
      * If we cleared 6+ disks this life OR failed >= consecutive_fail_cap times,
        consider prestiging (only if it would actually give a bonus)
      * Stall detection: if we go 4 prestiges with no new highest disk, terminate
    """
    main.gs = main.GameState()
    main.gs.current_dp = main.NEW_GAME_STARTER_DP
    main.recompute_legacy_bonuses()
    main.recompute_stats()

    history = []
    total_t = 0.0
    cleared_this_life = 0
    consec_fails = 0
    prestiges_since_new_highest = 0
    last_highest_order = 0

    while total_t < real_time_limit:
        highest_order = main.get_highest_cleared_order()
        # Frontier = next not-yet-cleared disk
        next_order = highest_order + 1
        if next_order > len(main.DISK_LETTERS):
            break  # cleared Z:
        target = main.DISK_LETTERS[next_order - 1] + ':'

        # Spend before the attempt
        buy_legacies_greedy()
        buy_skills_greedy()

        main.start_session_pure(target)
        result = simulate_session(time_step=1.0)
        total_t += result['sim_seconds']

        dp_gained, lp_gained = main.end_session_pure(result['success'])

        rec = {
            'time_sec': round(total_t, 1),
            'disk': target,
            'success': result['success'],
            'sess_t': round(result['sim_seconds'], 1),
            'dp_gained': dp_gained,
            'lp_gained': lp_gained,
            'dp_bal': main.gs.current_dp,
            'lp_bal': main.gs.unspent_lp,
            'prestige': main.gs.prestige_count,
            'highest': main.gs.highest_disk_cleared or '-',
            'M': round(main.gs.current_M, 2),
            'R': round(main.gs.current_R, 2),
            'A': round(main.gs.current_A, 2),
            'autocps': round(main.gs.current_autoclick, 2),
            'E': round(main.gs.current_E, 2),
            'skill_nodes': len(main.gs.purchased_nodes),
            'rep_stacks': sum(main.gs.purchased_repeatable.values()),
            'legacies': len(main.gs.purchased_legacy),
            'cleaned': result['cleaned'],
            'shatters': result['shatters'],
        }
        history.append(rec)
        if verbose:
            mark = 'WIN ' if result['success'] else 'FAIL'
            print(f"{rec['time_sec']:>7.1f}s  {rec['disk']}  {mark}  "
                  f"sess={rec['sess_t']:>5.1f}s  "
                  f"DP={rec['dp_bal']:>14,}  M={rec['M']:>10.0f}  "
                  f"R={rec['R']:>6.2f}  A={rec['A']:>10.0f}  "
                  f"acps={rec['autocps']:>9.0f}  "
                  f"nodes={rec['skill_nodes']}/{rec['rep_stacks']}/{rec['legacies']}  "
                  f"P#{rec['prestige']}")

        if result['success']:
            consec_fails = 0
            cleared_this_life += 1
        else:
            consec_fails += 1

        # Stall detection — if we haven't progressed past last_highest after 3 prestiges, give up
        cur_highest_order = main.get_highest_cleared_order()
        if cur_highest_order > last_highest_order:
            prestiges_since_new_highest = 0
            last_highest_order = cur_highest_order

        # Decide whether to prestige
        progressed = main.gs.total_lifetime_cleaned >= main.gs.prestige_lifetime_baseline + 50
        if consec_fails >= consecutive_fail_cap:
            if progressed:
                buy_legacies_greedy()
                main.perform_prestige_pure()
                history.append({'time_sec': round(total_t, 1), 'event': f'prestige #{main.gs.prestige_count}'})
                cleared_this_life = 0
                consec_fails = 0
                prestiges_since_new_highest += 1
                if prestiges_since_new_highest >= 3:
                    history.append({'time_sec': round(total_t, 1), 'event': 'STALL (3 prestiges no new highest)'})
                    break
            else:
                # Truly stuck — no way out
                history.append({'time_sec': round(total_t, 1), 'event': 'STALL (no progress, cannot prestige)'})
                break
        elif cleared_this_life >= 6 and result['success']:
            # Voluntary prestige after a good run
            if progressed and main.gs.unspent_lp >= 1:
                buy_legacies_greedy()
                main.perform_prestige_pure()
                history.append({'time_sec': round(total_t, 1), 'event': f'prestige #{main.gs.prestige_count}'})
                cleared_this_life = 0
                consec_fails = 0
                prestiges_since_new_highest += 1

    return history


# ============================================================================
# OUTPUT
# ============================================================================

def write_csv(history: list[dict], path: str):
    if not history:
        return
    keys = []
    for rec in history:
        for k in rec:
            if k not in keys:
                keys.append(k)
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
        w.writeheader()
        for rec in history:
            w.writerow(rec)


def print_summary(history: list[dict]):
    sessions = [r for r in history if 'event' not in r]
    events = [r for r in history if 'event' in r]
    if not sessions:
        print("(no sessions)")
        return
    last = sessions[-1]
    wins = [r for r in sessions if r.get('success')]
    fails = [r for r in sessions if not r.get('success')]
    print()
    print("=== Run summary ===")
    print(f"  Total sim time:    {last['time_sec']:.1f} s   ({last['time_sec']/60:.1f} min)")
    print(f"  Highest cleared:   {last['highest']}")
    print(f"  Total sessions:    {len(sessions)} ({len(wins)} wins, {len(fails)} fails)")
    print(f"  Total prestiges:   {len(events)}")
    print(f"  Final M / R / A:   {last['M']:.0f} / {last['R']:.2f} / {last['A']:.0f}")
    print(f"  Final auto-CPS:    {last['autocps']:.0f}")
    print(f"  Final DP balance:  {last['dp_bal']:,}")
    print(f"  Final LP balance:  {last['lp_bal']:,}")
    print(f"  Skill nodes owned: {last['skill_nodes']} / {len(main.SKILL_NODES)}")
    print(f"  Rep. stacks owned: {last['rep_stacks']}")
    print(f"  Legacies owned:    {last['legacies']} / {len(main.LEGACY_NODES)}")


# ============================================================================
# SWEEP MODE
# ============================================================================

def parse_sweep_args(sweep_args: list[str]) -> dict[str, list[float]]:
    """Parse `key=v1,v2,v3` strings into a dict."""
    out = {}
    for arg in sweep_args:
        key, vals = arg.split('=', 1)
        out[key.strip()] = [float(v) for v in vals.split(',')]
    return out


SWEEPABLE = {
    'hardness_growth':              'hardness_growth',
    'prestige_mult':                'prestige_mult',
    'rep_cost_growth_power':        'rep_cost_growth_power',
    'rep_cost_growth_botmult':      'rep_cost_growth_botmult',
    'rep_cost_growth_heatsink':     'rep_cost_growth_heatsink',
    'rep_cost_growth_alloc':        'rep_cost_growth_alloc',
    'rep_max_stacks_power':         'rep_max_stacks_power',
    'rep_max_stacks_botmult':       'rep_max_stacks_botmult',
    'rep_max_stacks_heatsink':      'rep_max_stacks_heatsink',
    'rep_max_stacks_alloc':         'rep_max_stacks_alloc',
    'cascade_scale':                'cascade_scale',
}


def run_sweep(sweep_grid: dict[str, list[float]], real_time_limit: float, csv_path: str | None):
    """Cross-product over the sweep_grid. For each combo, run a sim and record the outcome."""
    keys = list(sweep_grid.keys())
    combos = list(product(*[sweep_grid[k] for k in keys]))
    print(f"Running sweep: {len(combos)} configurations")

    results = []
    for combo in combos:
        kwargs = {SWEEPABLE[k]: v for k, v in zip(keys, combo)}
        # Cast max-stacks to int where appropriate
        for k in kwargs:
            if 'max_stacks' in k:
                kwargs[k] = int(kwargs[k])
        cfg = BalanceConfig(**kwargs)
        cfg.apply()
        history = run_full_simulation(real_time_limit=real_time_limit, verbose=False)
        sessions = [r for r in history if 'event' not in r]
        events = [r for r in history if 'event' in r]
        last = sessions[-1] if sessions else {}
        wins = [r for r in sessions if r.get('success')]
        stalled = any('STALL' in r.get('event', '') for r in events)
        result = {
            **{k: v for k, v in zip(keys, combo)},
            'total_time_min': round(last.get('time_sec', 0) / 60, 1),
            'highest': last.get('highest', '-'),
            'sessions': len(sessions),
            'wins': len(wins),
            'fails': len(sessions) - len(wins),
            'prestiges': len(events) - (1 if stalled else 0),
            'final_M': last.get('M', 0),
            'final_autocps': last.get('autocps', 0),
            'final_dp': last.get('dp_bal', 0),
            'stalled': stalled,
        }
        results.append(result)
        print(f"  {dict(zip(keys, combo))}  →  {result['highest']}  in {result['total_time_min']:.1f}m  "
              f"P#{result['prestiges']}  M={result['final_M']:.0f}  "
              f"acps={result['final_autocps']:.0f}{' [STALL]' if stalled else ''}")

    if csv_path:
        with open(csv_path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            w.writeheader()
            for r in results:
                w.writerow(r)
        print(f"\nSweep results -> {csv_path}")
    return results


# ============================================================================
# CLI
# ============================================================================

def main_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', help='Output CSV (single-run mode) or sweep results CSV')
    parser.add_argument('--verbose', '-v', action='store_true', help='Per-session log')
    parser.add_argument('--max-real-time', type=float, default=7200.0,
                        help='Real-time cap for the simulated player (default: 7200s = 2h)')
    parser.add_argument('--sweep', nargs='+', default=None,
                        help='Sweep mode: key=v1,v2,v3 ...')
    args = parser.parse_args()

    if args.sweep:
        grid = parse_sweep_args(args.sweep)
        unknown = [k for k in grid if k not in SWEEPABLE]
        if unknown:
            print(f"Unknown sweep keys: {unknown}", file=sys.stderr)
            print(f"Available: {list(SWEEPABLE.keys())}", file=sys.stderr)
            sys.exit(1)
        run_sweep(grid, real_time_limit=args.max_real_time, csv_path=args.csv)
    else:
        # Single run with current defaults
        BalanceConfig().apply()
        history = run_full_simulation(real_time_limit=args.max_real_time, verbose=args.verbose)
        if args.csv:
            write_csv(history, args.csv)
            print(f"CSV -> {args.csv}")
        print_summary(history)


if __name__ == "__main__":
    main_cli()

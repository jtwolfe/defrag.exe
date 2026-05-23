"""Narrow probe — find the (hg, pm) combo where maxed clears Z in 600-850s."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import main
from balance_sim import simulate_session, BalanceConfig


def setup_maxed_player(prestige_count: int):
    main.gs = main.GameState()
    for n in main.LEGACY_NODES:
        main.gs.purchased_legacy.add(n['id'])
    for n in main.SKILL_NODES:
        main.gs.purchased_nodes.add(n['id'])
        if n['effect']['type'] == 'time':
            main.gs.extra_timer_secs += n['effect']['value']
    for n in main.REPEATABLE_NODES:
        main.gs.purchased_repeatable[n['id']] = n['max_stacks']
    main.gs.prestige_count = prestige_count
    main.gs.highest_disk_cleared = 'Y:'
    main.recompute_legacy_bonuses()
    main.recompute_stats()


def probe(prestige_count, hardness_growth, prestige_mult, cascade_scale):
    BalanceConfig(hardness_growth=hardness_growth,
                  prestige_mult=prestige_mult,
                  cascade_scale=cascade_scale).apply()
    setup_maxed_player(prestige_count)
    z_h = main.DISKS['Z:']['hardness']
    main.start_session_pure('Z:')
    result = simulate_session(time_step=1.0)
    return {
        'hg': hardness_growth, 'pm': prestige_mult, 'cs': cascade_scale,
        'pc': prestige_count, 'z_h': z_h,
        'M': main.gs.current_M, 'acps': main.gs.current_autoclick,
        'res': 'WIN' if result['success'] else 'FAIL',
        'sess': result['sim_seconds'], 'final_frag': main.gs.fragmentation,
    }


def main_cli():
    print("Target: clear Z in 600-850s (close to ~871s timer)")
    print()
    # Narrow on the sweet spot. Vary hg finely + try different prestige counts.
    for pc in [3, 5, 8, 12]:
        print(f"\n=== prestige_count = {pc} ===")
        for hg in [1.55, 1.58, 1.60, 1.62]:
            for pm in [0.50, 0.75, 1.0]:
                r = probe(pc, hg, pm, 0.50)
                marker = " *** IN-BAND" if r['res'] == 'WIN' and 500 <= r['sess'] <= 870 else ""
                marker += " >> NEAR-TIMER" if r['res'] == 'WIN' and 650 <= r['sess'] <= 850 else ""
                print(f"  hg={r['hg']:.2f} pm={r['pm']:.2f} P#{r['pc']:>2} | "
                      f"Z_h={r['z_h']:>10,.0f} | M={r['M']:>6.0f} acps={r['acps']:>5.0f} | "
                      f"{r['res']} sess={r['sess']:>4.0f}s frag={r['final_frag']:>5.1f}%{marker}")


if __name__ == "__main__":
    main_cli()

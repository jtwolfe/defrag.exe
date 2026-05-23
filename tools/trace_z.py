"""Trace one Z: session under maxed player to see why simulator fails."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import main
from balance_sim import BalanceConfig

BalanceConfig(hardness_growth=1.25, prestige_mult=0.5, cascade_scale=0.0).apply()
main.gs = main.GameState()
for n in main.LEGACY_NODES:
    main.gs.purchased_legacy.add(n['id'])
for n in main.SKILL_NODES:
    main.gs.purchased_nodes.add(n['id'])
    if n['effect']['type'] == 'time':
        main.gs.extra_timer_secs += n['effect']['value']
for n in main.REPEATABLE_NODES:
    main.gs.purchased_repeatable[n['id']] = n['max_stacks']
main.gs.prestige_count = 10
main.gs.highest_disk_cleared = 'Y:'
main.recompute_legacy_bonuses()
main.recompute_stats()

d = main.DISKS['Z:']
print(f"Z hardness: {d['hardness']}")
print(f"Z cascade:  {d['cascade_chance']}")
print(f"Z shatter:  {d['shatter']}")
print(f"Z file mix: {d['file_mix']}")
print(f"M={main.gs.current_M:.2f}, R={main.gs.current_R:.2f}, A={main.gs.current_A:.2f}, "
      f"autocps={main.gs.current_autoclick:.0f}, E={main.gs.current_E:.2f}")
print(f"FR={main.gs.current_FR:.3f}, vs_power={main.gs.current_vs_power_mult}, "
      f"type_costs={main.gs.current_type_costs}")

main.start_session_pure('Z:')
print(f"\nInitial frag: {main.gs.fragmentation:.2f}% ({main.gs.fragmented_count} cells), "
      f"timer={main.gs.time_left}s")

# Count file types initially
from collections import Counter
types_init = Counter()
for row in main.gs.grid:
    for cell in row:
        if cell.state == 'fragmented':
            types_init[cell.file_type] += 1
print(f"  Initial fragmented breakdown: {dict(types_init)}")

# Tick 20s
for t in range(20):
    real_cps = min(2.0 * math.exp(-main.gs.current_autoclick / 25.0), main.gs.current_R)
    per_click = main.gs.current_M * main.gs.current_E * main.gs.current_click_multi
    per_click *= (1 + main.gs.current_crit_chance)
    manual_p = real_cps * per_click
    auto_p = main.gs.current_autoclick * per_click
    a_p = main.gs.current_A * main.gs.current_E
    total = manual_p + auto_p + a_p
    pre = main.gs.fragmented_count
    cleaned = main.apply_power(total)
    pre_shat = main.gs.session_shatter_events
    main.apply_refragmentation(1.0)
    types = Counter()
    for row in main.gs.grid:
        for cell in row:
            if cell.state == 'fragmented':
                types[cell.file_type] += 1
    print(f"t={t:>2}s: frag={main.gs.fragmented_count:>4}={main.gs.fragmentation:>5.2f}%  "
          f"cleaned={cleaned:>4}  shatter_events_so_far={main.gs.session_shatter_events:>4}  "
          f"types={dict(types)}  power={total:.0f}")
    if main.gs.fragmentation <= main.COMPLETION_FRAG_PERCENT:
        print("WIN!")
        break

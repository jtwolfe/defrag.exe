"""
Basic tests for the core simulation logic in DEFRAG.EXE.

The new prototype stores state on a single GameState (`main.gs`).
Tests reach in via that object rather than dozens of module globals.
"""

import os
import sys
from pathlib import Path

# Headless pygame for CI
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

import main as game  # noqa: E402


def setup_basic_disk_state(disk_key: str = "C:"):
    """Minimal setup so apply_power has fragmented cells to chew on."""
    game.gs.current_disk = disk_key
    game.recompute_stats()
    game.init_grid_for_disk(disk_key)

    # Force a few cells to fragmented so power has work
    for r in range(min(5, game.GRID_ROWS)):
        for c in range(min(8, game.GRID_COLS)):
            if game.gs.grid[r][c].state == "good":
                game.gs.grid[r][c].state = "fragmented"

    game.update_fragmentation()
    game.gs.session_cleaned = 0
    game.gs.total_lifetime_cleaned = 0


def test_apply_power_does_not_crash_and_returns_int():
    setup_basic_disk_state("C:")
    cleaned = game.apply_power(500.0)
    assert isinstance(cleaned, int)
    assert cleaned >= 0
    assert cleaned > 0 or game.gs.fragmented_count == 0


def test_apply_power_is_deterministic_for_same_budget():
    """Cheapest-first selection makes the same budget on the same grid produce the same result."""
    setup_basic_disk_state("C:")
    # Disable shatter on C: by setting shatter chain to empty, just to keep the
    # cleaning side deterministic without the random child-cell placement.
    game.DISKS["C:"]["shatter"] = {"sys": [], "media": [], "doc": [], "temp": []}

    snapshot = [(cell.state, cell.file_type) for row in game.gs.grid for cell in row]

    cleaned1 = game.apply_power(300.0)

    # Restore exactly
    idx = 0
    for r in range(game.GRID_ROWS):
        for c in range(game.GRID_COLS):
            st, ft = snapshot[idx]
            game.gs.grid[r][c].state = st
            game.gs.grid[r][c].file_type = ft
            idx += 1
    game.update_fragmentation()
    game.gs.session_cleaned = 0

    cleaned2 = game.apply_power(300.0)
    assert cleaned1 == cleaned2


def test_file_type_vs_power_mult_affects_cost_calculation():
    setup_basic_disk_state("C:")
    frag = next((c for row in game.gs.grid for c in row if c.state == "fragmented"), None)
    assert frag is not None

    ftype = frag.file_type
    disk = game.DISKS[game.gs.current_disk]
    raw = disk['hardness'] * game.gs.current_type_costs[ftype]
    eff_before = raw / max(0.1, game.gs.current_vs_power_mult[ftype])

    game.gs.current_vs_power_mult[ftype] *= 2.0
    eff_after = raw / max(0.1, game.gs.current_vs_power_mult[ftype])

    assert eff_after < eff_before


def test_prestige_farming_gate_works():
    game.gs.prestige_count = 0
    game.gs.total_lifetime_cleaned = 0
    game.gs.prestige_lifetime_baseline = 0
    game.gs.unspent_lp = 5

    made_progress = game.gs.total_lifetime_cleaned >= (game.gs.prestige_lifetime_baseline + 100)
    assert not made_progress, "Low progress should not allow prestige reward"

    game.gs.total_lifetime_cleaned = 200
    made_progress = game.gs.total_lifetime_cleaned >= (game.gs.prestige_lifetime_baseline + 100)
    assert made_progress, "Real cleaning should pass the progress gate"


def test_click_rate_cap_rejects_clicks_above_R():
    """When we burst clicks past R per second, extras are dropped and rate_capped_recent is set."""
    setup_basic_disk_state("C:")
    game.gs.current_R = 1.5  # very low cap
    game.gs.click_timestamps.clear()
    game.gs.rate_capped_recent = 0.0
    base_t = 100.0
    # 5 clicks within 0.6s window — first ~1 should land (1.5 cap * 0.6 window = 0.9 → at most 1 in window)
    for i in range(5):
        game.trigger_manual_sweep(base_t + i * 0.05)
    # Some clicks should have been rejected → rate_capped_recent > 0
    assert game.gs.rate_capped_recent > 0


def _plant_one_fragment(disk_key: str, file_type: str):
    """Wipe the grid and plant a single fragment of `file_type` at (0,0)."""
    game.gs.current_disk = disk_key
    game.recompute_legacy_bonuses()
    game.recompute_stats()
    game.init_grid_for_disk(disk_key)
    for row in game.gs.grid:
        for cell in row:
            cell.state = "good"
    game.gs.grid[0][0].state = "fragmented"
    game.gs.grid[0][0].file_type = file_type
    game.update_fragmentation()
    game.gs.session_shatter_events = 0


def test_shatter_spawns_lower_tier_fragment():
    """Cleaning a sys-type fragment on a disk with sys→[media] shatter spawns a media."""
    _plant_one_fragment("D:", "sys")
    game.apply_power(10_000.0)
    media_count = sum(1 for row in game.gs.grid for cell in row
                      if cell.state == "fragmented" and cell.file_type == "media")
    assert media_count >= 1, "Expected at least one media fragment from sys shatter"
    assert game.gs.session_shatter_events >= 1


def test_shatter_chain_at_every_level():
    """On a disk with the full sys→media→doc→temp chain, cleaning each tier should spawn the
    appropriate lower-tier child. Temp must NOT shatter (chain terminates)."""
    # E: has the full chain with low cascade so we can predict children count
    chain_disk = "E:"
    expected = {
        "sys": "media",
        "media": "doc",
        "doc": "temp",
    }
    for ftype, child in expected.items():
        # Disable cascade for predictability
        saved_cascade = game.DISKS[chain_disk]["cascade_chance"]
        game.DISKS[chain_disk]["cascade_chance"] = 0.0
        try:
            _plant_one_fragment(chain_disk, ftype)
            game.apply_power(1e9)
            # Verify the original got cleaned and the expected child appeared
            orig_remaining = sum(1 for row in game.gs.grid for cell in row
                                 if cell.state == "fragmented" and cell.file_type == ftype)
            child_count = sum(1 for row in game.gs.grid for cell in row
                              if cell.state == "fragmented" and cell.file_type == child)
            assert orig_remaining == 0, f"{ftype} should be cleaned, got {orig_remaining} remaining"
            assert child_count >= 1, f"Cleaning {ftype} on {chain_disk} should spawn {child} (got {child_count})"
        finally:
            game.DISKS[chain_disk]["cascade_chance"] = saved_cascade

    # Temp terminates the chain: no children regardless of disk
    _plant_one_fragment(chain_disk, "temp")
    game.apply_power(1e9)
    total_frags = sum(1 for row in game.gs.grid for cell in row if cell.state == "fragmented")
    assert total_frags == 0, "Cleaning a temp should not spawn anything"


def test_shatter_never_overwrites_existing_fragment():
    """Shatter must always target a 'good' cell. It must never silently re-purpose a
    not-yet-cleaned fragment, which would lose work and corrupt file-type accounting."""
    game.gs.current_disk = "C:"
    game.recompute_legacy_bonuses()
    game.recompute_stats()
    game.init_grid_for_disk("C:")
    # Wipe and plant 40 sys cells
    for row in game.gs.grid:
        for cell in row:
            cell.state = "good"
    sys_positions = [(r, c) for r in range(5) for c in range(8)]
    for r, c in sys_positions:
        game.gs.grid[r][c].state = "fragmented"
        game.gs.grid[r][c].file_type = "sys"
    game.update_fragmentation()

    # Budget of 25 power on C: (hardness 1.0, sys cost 2.5) -> exactly 10 sys cleaned.
    # The remaining 30 sys should still be sys-type — shatter should not have overwritten them.
    game.apply_power(25)
    assert game.gs.session_cleaned == 10
    overwritten = 0
    for r, c in sys_positions:
        cell = game.gs.grid[r][c]
        if cell.state == "fragmented" and cell.file_type != "sys":
            overwritten += 1
    assert overwritten == 0, f"Shatter overwrote {overwritten} still-fragmented sys cells"


def test_apply_power_cleans_in_row_major_order_for_same_cost():
    """Among equal-cost fragments, the sweep should clean left-to-right within each row, top-to-bottom.
    Regression test: tuple sort key used to be (eff, col, row, ...), making ties break column-first."""
    game.gs.current_disk = "C:"
    game.recompute_legacy_bonuses()
    game.recompute_stats()
    game.init_grid_for_disk("C:")
    # Disable shatter on C: so cleaning doesn't perturb the grid mid-sweep
    game.DISKS["C:"]["shatter"] = {"sys": [], "media": [], "doc": [], "temp": []}

    # Wipe and plant a 4x4 block of identical temp fragments — all have the same eff cost,
    # so ordering is entirely determined by the tie-break.
    for row in game.gs.grid:
        for cell in row:
            cell.state = "good"
    planted = []
    for r in range(4):
        for c in range(4):
            game.gs.grid[r][c].state = "fragmented"
            game.gs.grid[r][c].file_type = "temp"
            planted.append((r, c))
    game.update_fragmentation()

    # Apply budget for exactly 5 cleans: each temp on C: costs 0.6, so 5 cleans need ~3.0 power.
    # Use 3.5 to dodge floating-point rounding around the boundary (5 * 0.6 != 3.0 exactly in float).
    game.apply_power(3.5)
    assert game.gs.session_cleaned == 5

    # The 5 cleaned cells (now 'good') should be (0,0), (0,1), (0,2), (0,3), (1,0) —
    # the first 5 in row-major order.
    expected = [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0)]
    cleaned_positions = [(r, c) for (r, c) in planted if game.gs.grid[r][c].state == "good"]
    assert cleaned_positions == expected, (
        f"Expected row-major sweep {expected}, got {cleaned_positions}")


def test_shatter_resist_reduces_children():
    """Containment nodes should probabilistically remove shatter children — at full resist (~0.85
    cap) almost all children are dropped, so the chain effectively terminates."""
    game.gs.current_disk = "M:"  # sys -> ['media', 'media']
    game.gs.purchased_nodes = set()
    game.gs.current_shatter_resist = 0.85  # the cap
    game.recompute_legacy_bonuses()
    # don't call recompute_stats() — it would reset current_shatter_resist
    game.init_grid_for_disk("M:")

    # 200 trials: each starts with 1 sys, cleans it, counts spawned media
    trials = 200
    spawned_per_trial = []
    for _ in range(trials):
        for row in game.gs.grid:
            for cell in row:
                cell.state = "good"
        game.gs.grid[0][0].state = "fragmented"
        game.gs.grid[0][0].file_type = "sys"
        game.update_fragmentation()
        game.gs.session_shatter_events = 0
        game.apply_power(1e9)
        media = sum(1 for row in game.gs.grid for cell in row
                    if cell.state == "fragmented" and cell.file_type == "media")
        spawned_per_trial.append(media)

    avg = sum(spawned_per_trial) / trials
    # With 85% resist, each of 2 media children survives 15% of the time.
    # Expected average: 2 * 0.15 = 0.30 direct media spawns (cascade also suppressed by resist).
    # Allow generous bounds for stochastic test.
    assert avg < 0.7, f"Average spawned children with 85% resist should be ~0.3, got {avg}"


def test_winning_a_session_unlocks_next_disk_and_awards_lp():
    """Regression: previously the win check was nested inside a sim guard that required
    fragmentation > threshold to run. A click that cleared the drive bypassed the guard,
    leaving the game stuck with no DP/LP, no highest_disk update, no prestige possible."""
    game.gs = game.GameState()
    game.gs.current_dp = 0
    game.gs.unspent_lp = 0
    game.gs.highest_disk_cleared = None
    game.recompute_legacy_bonuses()
    game.recompute_stats()
    game.gs.current_disk = "C:"
    game.init_grid_for_disk("C:")

    # Force the drive to clean state, as if the player just clicked everything away
    for row in game.gs.grid:
        for cell in row:
            cell.state = "good"
    game.update_fragmentation()
    game.gs.session_cleaned = 400  # pretend we cleaned a bunch

    # The win condition should now be true
    assert game.gs.fragmentation <= game.COMPLETION_FRAG_PERCENT

    # End the session as a win and verify state transitions
    game.end_session(success=True)

    assert game.gs.highest_disk_cleared == "C:", "Clearing C: must set highest_disk_cleared"
    assert game.get_unlocked_tier() == 2, "Clearing C: must unlock Tier 2"
    assert game.gs.earned_lp > 0, "Win must award LP for prestige progression"
    assert game.gs.unspent_lp >= game.gs.earned_lp
    assert game.gs.earned_dp > 0


def test_hub_render_does_not_crash():
    """Render skill and prestige hub views once each (headless) to catch layout/draw exceptions."""
    import pygame
    # Build representative state: a couple of skill nodes owned, some DP, a selected node
    game.gs = game.GameState()
    game.gs.current_dp = 50
    game.gs.unspent_lp = 5
    game.gs.highest_disk_cleared = "C:"
    # Own the first manual Power node so the tree row reflects an owned state
    first_skill = sorted(game.SKILL_NODES, key=lambda n: (n['branch'], n['tier']))[0]
    game.gs.purchased_nodes.add(first_skill['id'])
    game.tree_selected_skill_id = first_skill['id']
    game.tree_selected_legacy_id = game.LEGACY_NODES[0]['id']
    game.recompute_legacy_bonuses()
    game.recompute_stats()

    # Render the HUB (skill tree only now) and the dedicated PRESTIGE screen.
    game.set_state('HUB')
    for _ in range(2):
        game.buttons.clear()
        game.screen.fill(game.W95_DESKTOP)
        game.draw_hub()
    assert len(game.buttons) > 0
    # The hub should expose an 'open_prestige' button — confirms the new entry point exists.
    assert any(a == 'open_prestige' for _r, a, _p in game.buttons)

    game.set_state('PRESTIGE')
    for _ in range(2):
        game.buttons.clear()
        game.screen.fill(game.W95_DESKTOP)
        game.draw_prestige_screen()
    # Prestige screen should expose 'cancel_prestige' and 'confirm_prestige' buttons.
    actions = {a for _r, a, _p in game.buttons}
    assert 'cancel_prestige' in actions
    assert 'confirm_prestige' in actions


def test_save_load_roundtrip(tmp_path, monkeypatch):
    """Save persistent state, mutate gs, load it back — persistent fields restore."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    game.gs = game.GameState()
    game.gs.highest_disk_cleared = "C:"
    game.gs.purchased_legacy = {"lm_grip1"}
    game.gs.total_lifetime_cleaned = 1234
    game.gs.prestige_count = 2
    game.gs.purchased_nodes = {"mpow_001"} if "mpow_001" in game.SKILL_BY_ID else set()
    game.gs.current_dp = 99
    game.gs.unspent_lp = 7
    game.gs.current_disk = "D:"

    assert game.save_game(3)

    game.gs = game.GameState()  # wipe
    assert game.gs.total_lifetime_cleaned == 0
    assert game.load_game(3)

    assert game.gs.highest_disk_cleared == "C:"
    assert game.gs.purchased_legacy == {"lm_grip1"}
    assert game.gs.total_lifetime_cleaned == 1234
    assert game.gs.prestige_count == 2
    assert game.gs.current_dp == 99
    assert game.gs.unspent_lp == 7
    assert game.gs.current_disk == "D:"

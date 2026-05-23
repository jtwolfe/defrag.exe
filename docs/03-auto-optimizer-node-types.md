# Auto Optimizer — Detailed Node Types

**Branch Philosophy**: The background process should feel like a real, improving operating system service. Every node makes the drive slowly get better even when the player is doing nothing. The fantasy is "I set this up better and now it just works while I do other things."

All bonuses are continuous rate improvements. No "activate background mode" buttons.

## Primary Stats This Branch Affects

- `A` — Auto Speed (clusters moved per second by the background process)
- `E` — Efficiency (how clean the background moves are)
- `FR` — Fragmentation Resistance (how much normal file writes re-fragment the drive)
- Small contributions to `M` via synergy nodes

The Auto branch is the main way "mostly idle" or "background tab" playstyles stay viable on long disks.

---

## Node Type Categories

### Type A1 — Raw Throughput
Direct increases to how fast the background process moves clusters.

This is the simplest and most important line. Many small-to-medium +% nodes.

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Faster Head | +32% Auto Speed (`A`) | Tier 1 / C: | Core early pickup |
| Better Scheduler | +26% Auto Speed | Tier 1 / C: | |
| DMA Optimization | +22% Auto Speed | Tier 2 / D: | |
| Parallel Passes | +18% Auto Speed | Tier 2 / D: | |
| Cached Metadata | +15% Auto Speed | Tier 3 / E: | |
| Predictive Readahead | +12% Auto Speed | Tier 3 / E: | |
| Enterprise Firmware | +10% Auto Speed | Tier 4 / F: | Late diminishing |

**Cumulative** from this type alone can easily reach **+2.8x – 3.2x** Auto Speed by deep investment.

### Type A2 — Efficiency & Waste Reduction
Improves how *good* the auto moves are (less re-fragmentation created by the act of defragging itself).

Very valuable on high Write Intensity disks.

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Smart Placement | +18% Efficiency (`E`) for auto moves | Tier 2 / D: | |
| Minimal Disturbance | +14% Efficiency for auto | Tier 2 / D: | |
| Gap Filling Heuristic | +11% Efficiency for auto + small global `E` | Tier 3 / E: | |
| Coalescing Engine | +9% Efficiency for auto | Tier 3 / E: | |
| Zero-Fragment Writes | +7% Efficiency for auto + 4% global `FR` | Tier 4 / F: | Excellent late node |

This line becomes disproportionately strong on disks E: and beyond.

### Type A3 — Fragmentation Resistance (The "Write Defense" Line)
Directly attacks the problem of new files constantly messing up your progress.

This is one of the most thematic and important lines in the entire tree.

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Write Combining | +12% Fragmentation Resistance (`FR`) | Tier 1 / C: | First real defense against re-fragmentation |
| Deferred Allocation | +10% `FR` | Tier 2 / D: | |
| Extent-Based Allocator | +9% `FR` + small `E` | Tier 2 / D: | |
| Lazy Write Coalescer | +8% `FR` | Tier 3 / E: | |
| Journaling Bypass | +7% `FR` + 5% global `E` | Tier 3 / E: | |
| Perfect Preallocation | +6% `FR` + small Auto Speed | Tier 4 / F: | Very strong on high-write disks |

Players who heavily invest here will notice that their drive "stays clean" much longer even while using it.

### Type A4 — Scheduling & Opportunism
Makes the auto process smarter about *when* it works.

Includes idle bonuses, low-impact modes, and "work while the user is away" fantasy.

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Background Priority | +25% Auto Speed while player has not clicked for 8+ seconds | Tier 1 / C: | Core "walk away" node |
| Opportunistic Pass | +16% Auto Speed during long idle periods | Tier 2 / D: | |
| Low Impact Mode | Auto Speed reduced by only 15% while player is actively using the machine (normally would be -40%) | Tier 2 / D: | Huge quality of life |
| Night Shift | +12% Auto Speed during extended idle (>45 seconds) | Tier 3 / E: | |
| Always Respectful | Auto never slows down more than 8% even during heavy manual clicking | Tier 3 / E: | Pairs amazingly with Manual players |
| Silent Guardian | +8% permanent Auto Speed + strong idle bonus | Tier 4 / F: | Capstone for pure idle enjoyers |

This category is what makes the game feel good as a desktop companion / second-monitor experience.

### Type A5 — Auto → Manual Synergy (The Reverse Flow)
Nodes where investing in auto also makes manual clicking better.

These are the mirror of the M5 nodes and are critical for hybrid players.

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Pre-Mapped Regions | +12% Manual Power on clusters the auto has recently touched | Tier 2 / D: | "The auto warmed it up for you" |
| Stability Field | While auto has been running for 20+ seconds, +9% Manual Power | Tier 2 / D: | |
| Shared Free Space Map | +7% Manual Power + +5% Click Rate while auto is above 60% of its max speed | Tier 3 / E: | |
| Auto-Assisted Sweeps | +5% of current Auto Speed is added to Manual Power (hybrid conversion) | Tier 3 / E: | Very elegant |
| Unified Optimizer | +4% to both `M` and `A` at all times (small global hybrid) | Tier 4 / F: | Expensive but powerful |

These nodes are the main reason someone might invest in both branches instead of going all-in on one.

### Type A6 — Specialization & Conditions
More situational or "build-around" bonuses.

These often have conditions or focus on specific situations/file types.

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Temp File Sweeper | +40% Auto Speed vs Temp files | Tier 1 / C: | Excellent early clear speed |
| Media Background Mover | +20% Auto Speed vs Media files | Tier 3 / E: | Essential for later disks |
| System File Patience | +15% Auto Speed vs System files (but only when fragmentation is already <25%) | Tier 3 / E: | Risk/reward |
| Free Space Hoarder | +18% Auto Speed when free space is highly fragmented | Tier 2 / D: | Good on messy starting states |
| End-of-Disk Finisher | +25% Auto Speed when current fragmentation is below 15% | Tier 3 / E: | Helps push the last 10% faster |
| Long Haul Stabilizer | +9% `FR` + +6% `E` while working on the same disk for >25 minutes | Tier 4 / F: | Rewards staying on one disk longer |

---

## Balancing Philosophy for Auto

- Auto should be **weaker than heavily invested Manual** on short sessions and early disks.
- Auto should become **dominant or equal** on very long sessions and later disks (especially if the player has invested in A3 Resistance and A4 Scheduling).
- The best "set and forget" builds will combine A1 + A3 + A4 heavily.
- The hybrid nodes (A5) are what stop pure-auto players from feeling completely left behind when they occasionally want to click.

**Target power fantasy**:
- Early game (C: / D:): Manual feels faster and more exciting.
- Mid-to-late game (E: / F:): A well-specced auto is genuinely carrying you while you do other things, and manual is for "I want to finish this faster" bursts.

---

## Open Questions

- Should some A4 scheduling nodes have hard requirements (e.g. "you must not have clicked in the last 30 seconds") or just soft bonuses?
- Do we eventually want a "true background mode" checkbox that pauses the manual system entirely in exchange for even higher auto multipliers? (Probably not in the first version — keep it simple.)
- How visible should the current Auto Speed number be to the player?

This branch is now specified at the same depth as Manual.

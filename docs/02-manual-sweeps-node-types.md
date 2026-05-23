# Manual Sweeps — Detailed Node Types

**Branch Philosophy**: Every time the player clicks the Defrag Space, something measurable and better happens. All power comes from increasing the two numbers that define a click: **how much work one click does** and **how often they can do it**.

No special abilities. No cooldowns. No "big one-time moves". Pure rate improvement.

## Primary Stats This Branch Affects

- `M` — Manual Power (clusters moved per click)
- `R` — Click Rate (effective clicks per second)
- `E` — Efficiency (small secondary effect — manual moves are "cleaner")

Secondary goals:
- Make clicking feel increasingly rewarding as you invest.
- Create meaningful choice between "click more often" vs "each click is stronger".
- Provide light specialization (some lines favor burst clicking, others favor steady rhythm).

---

## Node Type Categories

We group nodes into 6 clean types. Each type has a natural progression of 3–5 nodes.

### Type M1 — Raw Power
Directly increases how many clusters one click moves.

**Design Pattern**: Several nodes with solid +% gains, getting slightly smaller as you go deeper (diminishing but still valuable).

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Stronger Arm | +28% Manual Power (`M`) | Tier 1 / C: | Core first purchase |
| Reinforced Head | +24% Manual Power | Tier 2 / D: | |
| Optimized Seek | +20% Manual Power | Tier 2 / D: | |
| Cluster Magnet | +18% Manual Power | Tier 3 / E: | |
| Precision Actuator | +15% Manual Power | Tier 3 / E: | Smaller but still good |
| Legacy Firmware | +12% Manual Power | Tier 4 / F: | Late diminishing return |

**Cumulative effect** (if all taken): roughly **+2.1x to +2.4x** Manual Power from this type alone.

### Type M2 — Click Frequency
Increases how fast the player can actually perform clicks.

This is the "attack speed" equivalent.

**Important**: We probably want a soft cap here. Real humans can't click 15 times per second usefully. So later nodes in this line can convert excess rate into something else (e.g. "overkill clicks give bonus power" or just smaller gains).

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Responsive UI | +22% Click Rate (`R`) | Tier 1 / C: | |
| Polled Input | +18% Click Rate | Tier 2 / D: | |
| Buffered Commands | +15% Click Rate | Tier 2 / D: | |
| Low Latency Driver | +12% Click Rate | Tier 3 / E: | |
| Muscle Memory | +10% Click Rate | Tier 3 / E: | |
| Hyperclick Heuristic | +8% Click Rate + small conversion of excess rate into power | Tier 4 / F: | Safety valve for very fast clickers |

**Design note**: This line should feel great for players who like active clicking, but not completely dominate the "mostly idle" playstyle.

### Type M3 — Move Quality / Cleanliness
Improves how *good* the clusters moved by manual clicks are.

Instead of raw quantity, you get better placement → higher `E` (Efficiency) on manual contribution, or reduced future fragmentation from those specific moves.

This is the "quality over quantity" line.

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Contiguous Planner | +15% Efficiency (`E`) on clusters moved by manual sweeps | Tier 2 / D: | |
| Defrag-Aware Allocator | +12% Efficiency on manual moves | Tier 2 / D: | |
| Lookahead Cache | +10% Efficiency on manual + small global `E` | Tier 3 / E: | |
| Perfect Contiguity | +8% Efficiency on manual moves | Tier 3 / E: | |
| Zero-Waste Seeker | +6% Efficiency on manual + converts some manual power into permanent small `E` | Tier 4 / F: | Prestige-friendly |

This line is especially valuable on later disks where re-fragmentation hurts more.

### Type M4 — Targeting Specialization
Makes manual clicks "smarter" about *which* fragments they move.

Because we don't want per-file clicking, this is expressed as **global % bonuses when certain file types are dominant**, or better effective power against hard-to-move files.

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Temp File Prioritizer | +35% effective Manual Power vs Temp files | Tier 1 / C: | Strong early game on C: and D: |
| Document Consolidator | +22% effective Manual Power vs Documents | Tier 2 / D: | |
| Media Relocator | +18% effective Manual Power vs Media files | Tier 3 / E: | Critical for mid-game scaling |
| System File Confidence | +12% effective Manual Power vs System files | Tier 3 / E: or E: completion | High risk/reward feel |
| Heavy File Specialist | +15% effective power vs Media + System combined | Tier 4 / F: | Late game keystone for this type |

These are **multiplicative with Raw Power** when the condition is met, so they stack beautifully.

### Type M5 — Manual → Auto Synergy
Nodes that make manual clicking also improve the automatic process (the heart of "both systems matter").

These are some of the most important nodes for making the game feel cohesive.

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Disturbance Mapping | Every manual click gives +3 seconds of +18% Auto Speed in the affected region | Tier 2 / D: | Feels like "waking up" the auto |
| Write Journal Sync | Manual sweeps reduce current re-fragmentation rate by 8% for 8 seconds | Tier 2 / D: | |
| Shared Optimizer | +6% global Auto Speed while you have clicked in the last 12 seconds | Tier 3 / E: | Strong "active player" reward |
| Coordinated Passes | Manual Power also contributes a small amount directly to Auto Speed (conversion) | Tier 3 / E: | Permanent small hybrid power |
| Full System Awareness | +4% to both `M` and `A` while clicking at least once every 5 seconds | Tier 4 / F: | Very strong late hybrid node |

### Type M6 — Click Rhythm / Playstyle
Slightly different flavors of how you like to click.

These nodes reward consistent behavior or specific rhythms without hard requirements.

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Steady Hand | +10% Manual Power if you have not let 4+ seconds pass without a click | Tier 2 / D: | Rewards active play |
| Burst Tolerance | +14% Manual Power for the first 3 clicks after 6+ seconds of no clicking | Tier 2 / D: | Rewards coming back and going hard |
| Marathon Clicker | Small stacking +% Manual Power that builds while clicking continuously (caps after 25 clicks) | Tier 3 / E: | For the really dedicated |
| Patient Operator | +9% Manual Power + +6% Efficiency if average click rate is below 1.2/sec over last 30s | Tier 3 / E: | Rewards relaxed clicking |
| Click Economy | Excess Click Rate above 4.5/sec is converted into +Manual Power at 60% efficiency | Tier 4 / F: | Safety for players who click extremely fast |

---

## Recommended Purchase Order Feel (Early Game)

1. Strongest early Raw Power (M1)
2. One Frequency node (M2) so clicking doesn't feel capped immediately
3. Temp File Prioritizer (M4) — big power spike on starting disk
4. First Synergy node (M5) — makes the two systems talk
5. Then branch into Quality (M3) and heavier specialization as disks get harder

---

## Balancing Notes

- **Total Manual Power multiplier** from the entire branch by late Tier 3/4 should be in the **4x – 7x** range depending how heavily the player invested here vs the other branches.
- Click Rate should probably top out around **3.5 – 4.5 effective clicks/sec** for normal humans. Anything higher should have heavy diminishing returns or conversion.
- The Synergy nodes (M5) are the "prestige insurance" — they make heavy manual investment still valuable even if the player eventually goes more idle on huge disks.

---

## Open Tuning Questions

- Do we show the player the current `M` and `R` numbers, or only the "clusters per second from manual" combined value?
- Should some M6 rhythm nodes be mutually exclusive (pick a playstyle)?
- How much should manual specialization beat pure auto on early disks? (Suggested: 30–50% faster if heavily invested, but auto catches up on very long idle sessions.)

This document is now detailed enough to assign actual point costs and run simulations.

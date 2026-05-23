# Disk Progression & Prestige Loop

**Design Goal**: Every new disk must feel like a real step up in challenge. The only way to keep up is through the skill tree + eventual prestige. Playtime per disk should be tunable via simulation.

## Disk Identity

Each disk is defined by:

- **Label** (`C:`, `D:`, `E:`, ...)
- **Capacity** (raw size in GB)
- **Base Fragmentation** (starting % of clusters that are fragmented)
- **Hardness Multiplier** (how expensive it is to move clusters on this disk)
- **File Type Mix** (what % of the drive is Temp / Documents / Media / System)
- **Write Intensity** (how fast normal "use" re-fragments the drive while you're working on it)
- **Completion Threshold** (what % fragmented you must reach to "finish" the disk)

## Proposed Disk Ladder (First 6 Disks)

| Disk | Capacity | Starting Frag | Hardness | Dominant File Types | Write Intensity | Base Session Timer | Est. Work Units (relative) |
|------|----------|---------------|----------|---------------------|-----------------|---------------------|----------------------------|
| C:   | 16 GB    | 65%           | 1.0x     | 40% Temp, 40% Docs, 15% Media, 5% System | Low             | 18–22 min           | 1.0 (baseline)             |
| D:   | 32 GB    | 72%           | 2.8x     | 25% Temp, 35% Docs, 30% Media, 10% System | Medium          | 24–28 min           | ~6–7x                      |
| E:   | 64 GB    | 78%           | 7.5x     | 15% Temp, 30% Docs, 35% Media, 20% System | Medium-High     | 26–32 min           | ~35–40x                    |
| F:   | 128 GB   | 81%           | 18x      | 10% Temp, 25% Docs, 40% Media, 25% System | High            | 28–35 min           | ~180x                      |
| G:   | 256 GB   | 84%           | 45x      | 5% Temp, 20% Docs, 45% Media, 30% System  | High            | 30–38 min           | ~900x+                     |
| H:   | 512 GB   | 87%           | 110x     | 5% Temp, 15% Docs, 50% Media, 30% System  | Very High       | 32–40 min           | ~4500x                     |

**Notes on scaling**:
- Capacity roughly doubles.
- Hardness grows faster than linear (roughly 2.5–2.8x per disk).
- Later disks are dominated by "heavy" files (Media + System) which the Filesystem Intelligence branch is meant to solve.
- Completion threshold gets stricter (you have to get it *cleaner* on bigger, stickier drives).

This combination easily produces the "10x harder" feeling the user wants while still being progressive.

---

## Completion & Gating Rules (Timed Session to 0%)

The core gate for every disk is now a **hard timed session**:

- When you begin working on a disk (or restart it after failure), you are given a **Session Timer** (starting time in minutes/seconds).
- Real time (or accelerated game time) ticks down continuously.
- Both Manual sweeps and Auto progress consume this timer at the same rate.
- **Success condition**: Reach **exactly 0% fragmentation** before the timer reaches zero.
- If the timer hits zero with any fragmentation remaining → the session "times out". The drive becomes unstable. You get partial rewards (some Defrag Points, maybe a small permanent bonus), but you do **not** unlock the next disk or full skill tree tier. You can restart the same disk with a fresh timer (possibly slightly shorter on repeat attempts).

This creates real pressure and makes every second count. Efficiency and resistance become as important as raw power, because re-fragmentation wastes precious time.

### Base Session Timers (Proposed Starting Values)

| Disk | Starting Session Time | Notes |
|------|-----------------------|-------|
| C:   | 18–22 minutes         | Generous tutorial disk |
| D:   | 24–28 minutes         | First real pressure |
| E:   | 26–32 minutes         | Gets tighter relative to work |
| F:   | 28–35 minutes         | Requires serious investment |
| G:   | 30–38 minutes         | Very tight on raw power alone |
| H:   | 32–40 minutes         | Only realistic with heavy Filesystem time investment |

These numbers are tunable. The key is that later disks give only modestly more time while requiring dramatically more work.

### How Filesystem Intelligence Extends Time

This is where the "NTFS/Black Magic" tree becomes uniquely powerful.

Several nodes in the Filesystem branch now **increase your starting Session Timer** for the current disk and/or all future disks. Some can even be purchased mid-session for emergency extensions.

Examples of time-related effects:
- +3 minutes to current session timer
- +8% base session time on this disk size and larger
- Permanent +45 seconds to all future session timers (prestige-friendly)
- "Emergency Maintenance Window" — one-time big extension bought with Defrag Points during a run

Buying time (via the Filesystem branch) between rounds becomes a legitimate strategic path alongside raw power. A player who heavily invests in time extensions and efficiency can beat later disks with less overall speed because they simply have more minutes to work with.

### Skill Tree Gating

- **Tier 1 nodes** (all branches): Available immediately on C:
- **Tier 2 nodes**: Unlock after successfully completing C: within the time limit
- **Tier 3 nodes**: Unlock after successfully completing D:
- **Tier 4 / Keystone nodes**: Unlock after completing E: or F:
- Time-extension nodes in the Filesystem branch are deliberately spread across tiers so you feel the need for them more as disks get harder.

This makes the tree itself part of the progression story.

---

## Prestige / "New Drive" Loop

### When Can You Prestige?
Two possible triggers (we can pick one or offer both):

**Option A — Drive Death (Thematic)**
- After completing a disk, you have a chance (or a button) to "retire the drive".
- The drive "dies" (platters degrade, bad sectors win, etc.).
- You get a new, bigger, blank drive with fresh high fragmentation.

**Option B — Player Choice (More Game-like)**
- At any time after completing the current disk, you can choose to prestige.
- This is the classic "I want the multipliers now" button.

Recommended: Let the player prestige after any disk completion, but the **amount of prestige currency** scales with how far they got and how clean they left the drive.

### Prestige Currency Sources (Lifetime Stats)
- Total clusters ever moved (across all runs)
- Number of disks fully completed
- Best "cleanliness" achieved on each disk size
- Total time spent with auto running
- Bonus for "one-life" runs (finishing several disks without prestiging)

### Reduced Prestige / Legacy System (New Direction)

Instead of big global multipliers on the main stats, we use a small, separate **Legacy Tree** (sometimes called the Prestige Tree or Career Tree).

This is a much more reduced system with fewer nodes. Its purpose is to give **permanent base improvements** that make every future run start stronger in foundational ways.

**How it works**:
- You earn **Legacy Points** when you successfully complete disks (especially on first clear or with good performance).
- These points are spent in a small always-available meta tree (separate from the per-run skill tree).
- The Legacy Tree has 4 light branches that directly improve the *base* values of the three main branches + time.

**Proposed Legacy Branches** (very reduced — aim for 3–5 nodes per branch total):

| Legacy Branch | What it Improves | Example Nodes |
|---------------|------------------|---------------|
| **Manual Legacy** | Base Manual Power and Click Rate | +8% base M, +6% base R, starting click feels stronger, etc. |
| **Auto Legacy** | Base Auto Speed + idle behavior | +10% base A, better starting idle priority, auto starts faster on new disks |
| **Time Legacy** | Base Session Timers + time efficiency | +2 min on all disks, +6% base session time, less time wasted on re-fragmentation at start |
| **Knowledge Legacy** (Filesystem flavor) | Starting advantages | Start with first Temp File node unlocked, better starting file type handling, small bad sector resistance, etc. |

This system is deliberately "reduced" — it should feel like meaningful permanent progress without becoming another deep skill tree.

Early prestiges give small but noticeable base buffs (e.g. +5–10% to one area).
Later prestiges let you push specific branches harder so your "new drive" starts with real advantages in the areas you care about most.

This pairs beautifully with the timed gate: investing Legacy Points into Time Legacy or Knowledge Legacy can be just as valuable as raw power for clearing later disks.

We can still have a few big "choose one" powerful legacy nodes at the very end of the tree for long-term players.

---

## Playtime Tuning Targets (Example)

Using the simulation model from `00-core-simulation-model.md`, we can set targets like:

| Disk | Target Playtime (active player, good tree progress) | Target if mostly idle |
|------|-----------------------------------------------------|-----------------------|
| C:   | 8–15 minutes                                        | 25–35 minutes         |
| D:   | 20–35 minutes                                       | 50–70 minutes         |
| E:   | 45–70 minutes                                       | 2–3 hours             |
| F:   | 90–140 minutes                                      | 4–6 hours             |

These are adjustable by changing:
- Base work units per disk
- Hardness curve
- How generous early skill tree nodes are
- How strong prestige multipliers get

Because every upgrade is just a number on `M`, `R`, `A`, `E`, we can write a tiny script later that says "with these exact nodes purchased, how long does Disk X take at 70% click uptime?"

---

## Open Questions for This System

1. Do we want one prestige currency that buys multipliers in any stat, or separate "Manual Legacy", "Auto Legacy", etc.?
2. Should prestige be the *only* way to get global multipliers, or do some very late skill tree nodes also give small permanent gains?
3. Do we show the player the "effective work remaining" number, or keep it hidden behind the pretty grid (recommended: hidden, only show % fragmented + estimated time at current rates)?

---

**Status**: This model is simulation-ready. Next step is writing the actual node lists in the branch documents so we can plug numbers into a calculator.

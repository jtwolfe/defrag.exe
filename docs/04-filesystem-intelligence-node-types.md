# Filesystem Intelligence — Detailed Node Types

**Branch Philosophy**: This is the "I understand how drives actually work" branch. It adds the realistic complexity (different file behaviors, bad sectors, write patterns, NTFS tricks) and turns that complexity into power.

Many nodes here are **conditional** or **unlocking** in nature. They are the main way the game becomes more interesting on larger, messier disks.

This branch also contains most of the cross-system synergy and the nodes that make later disks feel solvable instead of just "numbers go up more."

## Primary Stats This Branch Affects

- Unlocks and improves `FileTypeMultipliers` (the cost/benefit of moving different kinds of data)
- Improves `FR` (Fragmentation Resistance) in sophisticated ways
- Improves `E` (Efficiency) with real-world techniques
- Provides powerful hybrid multipliers between Manual and Auto
- Adds light "problem" mechanics (bad sectors) that become opportunities once solved

---

## Node Type Categories

### Type F1 — File Type Mastery
The core of "different data types matter."

Early nodes make easy files *easier*. Later nodes make hard files manageable.

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Temp File Expert | Temp files cost 35% less to move (effective +54% power vs them) | Tier 1 / C: | Huge early game accelerator |
| Document Streamliner | Documents cost 18% less to move | Tier 2 / D: | |
| Media File Specialist | Media files cost 22% less to move | Tier 3 / E: | **Critical** for E: and F: scaling |
| System File Confidence | System files cost 15% less to move + small risk of temporary slowdown | Tier 3 / E: | First taste of "dangerous but rewarding" |
| Heavy File Maestro | Media + System files both cost 12% less | Tier 4 / F: | Strong consolidation node |
| Universal Handler | All file types cost 6% less (global) | Tier 4 / F: | Expensive but clean |

These nodes are **multiplicative** with both Manual Power and Auto Speed when the relevant file type is being moved. This is how the game stays balanced as the disk composition gets worse.

### Type F2 — Bad Sector & Error Handling
Introduces light friction (bad sectors appear more on later disks) and then gives tools to deal with them.

Bad sectors can be modeled as:
- Small % of clusters that are "expensive" or "risky" to touch
- Or clusters that sometimes "fight back" and create extra fragmentation

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Bad Sector Awareness | First time you encounter bad sectors on a disk, you take 40% less penalty | Tier 2 / D: | Softens the first encounter |
| Remapping Intelligence | Bad sectors cost 25% less to work around | Tier 2 / D: | |
| Skip & Log | +8% global Efficiency when bad sectors are present on the current disk | Tier 3 / E: | Turns a negative into a small positive |
| Aggressive Remap | You can deliberately target bad sector clusters for high reward but temporary fragmentation spike | Tier 3 / E: | Optional high-skill play |
| Sector Blacklist | 15% chance to completely ignore a bad sector (no penalty, no progress on it) | Tier 4 / F: | Very strong on the worst disks |
| Forensic Recovery | Every bad sector successfully handled gives a small permanent +% to `FR` for the rest of the run | Tier 4 / F: | Long-term payoff |

This category lets us make later disks feel scarier without making them purely number walls.

### Type F3 — Advanced Allocation Techniques
Real-world filesystems tricks (extents, preallocation, MFT tricks, etc.) translated into % bonuses.

These are usually global and somewhat expensive.

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Extent Packing | +9% global Efficiency (`E`) | Tier 2 / D: | |
| Preallocation Cache | +7% `FR` + +4% Auto Speed | Tier 2 / D: | |
| MFT Zone Optimization | +6% `FR` + small Manual Power when fragmentation is already low | Tier 3 / E: | Excellent for the final 10% of a disk |
| Delayed Allocation | +8% `FR` when Write Intensity is Medium or higher | Tier 3 / E: | Situationally very strong |
| Online Defrag Capability | Auto can make progress even while heavy writes are happening (reduces the Write Intensity penalty by 30%) | Tier 4 / F: | One of the strongest late-game quality of life nodes |
| Perfect Layout Engine | +5% to `M`, `A`, and `E` while the drive is below 12% fragmented | Tier 4 / F: | Rewards actually finishing disks cleanly |

### Type F4 — Cross-System Synergy (The Glue)
These are the highest-value nodes in the entire tree for players who invest in more than one branch.

They are deliberately placed in the Filesystem branch so you have to "earn" the right to make Manual and Auto talk to each other.

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Unified Pass Planner | +10% Manual Power and +8% Auto Speed at the same time | Tier 3 / E: | Simple and extremely strong |
| Disturbance Sharing | Manual clicks increase nearby Auto Speed by an extra 12% (was 6–8% from Manual branch) | Tier 3 / E: | Amplifies existing synergy |
| Coordinated Free Space | Both systems get +6% power when working on the same 20% of the drive | Tier 3 / E: | Rewards paying attention to the grid |
| Feedback Loop | Every 10 seconds of continuous auto progress gives a stacking (capped) +3% Manual Power | Tier 4 / F: | Great for hybrid |
| Master Defragmenter | +4% global to `M`, `A`, `E`, and `FR` (small but applies to everything) | Tier 4 / F: | The ultimate "I maxed the tree" node |

These nodes are the main reason the three-branch structure feels good instead of like three separate games.

### Type F5 — Workload & Disk Condition Mastery
Nodes that care about the current state of the disk or the type of workload.

These become more relevant as you move through the disk ladder.

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| High-Fragmentation Specialist | +22% to both `M` and `A` while fragmentation is above 55% | Tier 2 / D: | Helps with the ugly starting state of new disks |
| Cleanup Finisher | +28% to both systems when fragmentation drops below 15% | Tier 3 / E: | Makes the last stretch much more satisfying |
| Write-Heavy Acclimation | +12% `FR` + +7% Auto Speed on disks with High or Very High Write Intensity | Tier 3 / E: | Directly counters the scaling problem on F: / G: |
| Long Session Stabilizer | Small stacking bonus to `E` and `FR` the longer you have been on the current disk (caps after 40 minutes) | Tier 4 / F: | Rewards not bouncing between disks |
| One-Pass Wonder | +15% global power if you have never let fragmentation rise more than 4% since starting the disk | Tier 4 / F: | Achievement-style playstyle reward |

### Type F6 — Prestige & Legacy Prep
Nodes that give small permanent or run-long benefits, or that specifically help after prestige.

These are the "I want my next life to be easier" investments.

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Institutional Knowledge | Start every new disk with +8% `FR` for the first 8 minutes | Tier 3 / E: | Helps the brutal early phase of a fresh drive |
| Muscle Memory | +5% Manual Power on the first disk after a prestige (decays over 20 minutes) | Tier 3 / E: | |
| Proven Layouts | +6% global `E` for the entire run after completing 3+ disks in one life | Tier 4 / F: | |
| Drive Historian | Small permanent +% to one chosen stat after prestiging (player picks which stat) | Tier 4 / F: | Very strong prestige synergy |
| Ghost in the Machine | After prestiging, you keep 3% of your best-ever `FR` from the previous life as a permanent bonus | Tier 4 / F: | Cool flavor + mechanical value |

These nodes are deliberately expensive and late so they feel like a real investment in your long-term "career" as a defragmenter.

### Type F7 — Session Time & Maintenance Windows (New Core Category)
This is the dedicated "buy more time" line that directly interacts with the timed 0% gate.

These nodes are the main way the Filesystem Intelligence branch lets players beat later disks without needing god-tier raw power. Time is now a first-class resource.

**Important Rule**: Time extensions are **only purchased between rounds** (after a disk attempt ends, success or failure). You cannot buy time while a session is actively running. This keeps the pressure pure during a run.

**Design Notes**:
- Most nodes give **permanent or scaling increases** to base session length.
- Some are one-time purchases you can make in the between-rounds shop using accumulated points.
- A few make time more efficient (less waste = effective extra time).

Example nodes:

| Node Name | Bonus | Tier / Disk Gate | Notes |
|-----------|-------|------------------|-------|
| Scheduled Service Lease | +5 minutes to current disk's base timer + +2 minutes to all future disks of this size | Tier 2 / D: | Strong early-mid investment |
| Enterprise Defrag License | +12% base Session Timer on this disk and all larger disks | Tier 3 / E: | Excellent scaling node |
| Background Daemon Priority | +90 seconds permanent to all future session timers | Tier 3 / E: | Very prestige-friendly |
| NTFS Online Extension Patch | While fragmentation is dropping, time passes 8% slower (effective time extension via efficiency) | Tier 3 / E: | Subtle but powerful on long runs |
| Corporate Maintenance Contract | +18% base session time on all disks | Tier 4 / F: | One of the strongest late-game time nodes |
| Ghost Process Allocation | After prestiging, you start the next life with +3 minutes on the first disk | Tier 4 / F: | Legacy time carry-over |
| Maintenance Window Expansion | Permanent +4 minutes to base timer on every disk size | Tier 4 / F: | Big, expensive, very satisfying |

**Strategic Role**:
Heavy investment in F7 lets a player clear later disks with more modest Manual/Auto power because they simply have more minutes to work with. This creates a genuine second axis of progression ("I can't make the drive faster, but I can give myself more time to finish it").

It also makes the Filesystem branch feel uniquely valuable compared to just stacking raw power in the first two branches.

---

## How This Branch Changes the Feel of the Game

- **Without Filesystem investment**: Later disks (E: onward) feel like a pure numbers slog. Media and System files are painful. Bad sectors are just annoying.
- **With moderate Filesystem investment**: Later disks feel *different* rather than just *harder*. You have tools that directly counter the new problems the disk ladder introduces.
- **With heavy Filesystem investment**: You start to feel like an expert. You know which file types to prioritize, when to push, when to let auto cook, and how to keep a giant drive surprisingly clean.

This is the branch that makes the "different disks get harder in interesting ways" fantasy actually deliver.

---

## Balancing Guidance

- File Type Mastery (F1) nodes should be some of the **highest priority** purchases once their relevant disk is unlocked.
- Bad Sector nodes (F2) should feel like they pay for themselves on the disks where bad sectors are common.
- The big hybrid nodes (F4) should be expensive enough that going deep in two branches feels like a real choice compared to maxing one branch + light Filesystem.
- **Type F7 (Session Time)** is now a first-class strategic path. Players should be able to clear some later disks primarily by buying a lot of extra time + efficiency rather than pure power. This is intentional and creates meaningful build variety.
- The reduced Legacy / Prestige tree (separate from the main skill tree) is the main way players get permanent base improvements across runs. F6 and F7 nodes that give legacy carry-over (starting time, starting knowledge, etc.) are especially valuable.

---

## Open Questions (Updated for Timed Sessions)

- Should time tick in real time even if the player walks away from the computer, or only while the game window is focused/active?
- Should there be any visual/audio warning when you're getting low on time (e.g. drive starts making worrying noises at 3 minutes left)?
- Should F7 time nodes be the primary way to make ultra-late disks (G:, H:, etc.) realistically completable, or should raw power still be able to brute-force them?

This completes the detailed node type breakdown for all three branches. The addition of Type F7 makes the Filesystem Intelligence branch a true third pillar alongside raw Manual and Auto power.

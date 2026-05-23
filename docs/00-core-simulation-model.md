# Core Simulation Model — Defrag Clicker

**Goal**: Everything must be simulatable with clean math so we can tune exact playtimes per disk.

## Fundamental Quantities

The entire game state can be reduced to a small number of numbers. Every skill node only touches these.

### Primary Rates

| Stat | Symbol | Meaning | Base Value (Disk C:) | Units |
|------|--------|---------|----------------------|-------|
| Manual Power | `M` | Clusters moved per single click | 100 | clusters/click |
| Click Rate | `R` | Effective clicks player can perform per second (after any soft limits) | 2.0 | clicks/sec |
| Auto Speed | `A` | Clusters the background process moves per second | 50 | clusters/sec |
| Efficiency | `E` | How "clean" moves are (higher = less future fragmentation created) | 1.0 | multiplier |

**Effective Progress Rate** (clusters cleaned per second when player is active):

```
Progress/sec = (M * R + A) * E
```

When the player is idle (not clicking), only `A * E` applies.

### Secondary / Situational Stats

These modify the above or the cost of work.

- `FragmentationResistance` (`FR`) — Reduces how much new writes re-fragment the drive.  
  New fragmentation generated = base_write_fragmentation * (1 - FR)

- `FileTypeMultipliers` — Map of data types to move difficulty:
  - `Temp`: easy (0.6x cost)
  - `Documents`: normal (1.0x)
  - `Media`: hard (1.8x cost)
  - `System`: very hard or locked until unlocked (2.5x+)

- `DiskWorkRequired` — Total "cluster-moves" needed to reach completion on current disk. This is the big number that scales per disk.

### Completion Definition

A disk is complete when remaining fragmentation work drops to 0 (or below a small threshold).

Work is reduced by `Progress/sec` over time.

---

## Disk Scaling Model (The Prestige Hook)

Every new disk must feel meaningfully harder. Two orthogonal levers we can combine:

### 1. Size Scaling (Capacity)
Disks increase in raw size:
- C:  16 GB
- D:  32 GB
- E:  64 GB
- F: 128 GB
- G: 256 GB
- etc. (doubling or 1.5x each time)

Bigger disk = more total clusters = more total work even at same fragmentation %.

### 2. Hardness / Stickiness Scaling (The "10x Harder" Feeling)
Later disks have "stickier" fragments:
- Higher base move cost per cluster
- Higher re-fragmentation rate from normal use
- Worse starting fragmentation distribution
- More "heavy" file types (more Media/System)

Example hardness multipliers per disk:
- C: 1.0x (baseline)
- D: 2.5x
- E: 6x
- F: 15x
- G: 40x

Combined with size, this easily gives 8-12x more work per disk.

### 3. Prestige / Legacy Multipliers
Prestige gives permanent global multipliers to `M`, `R`, `A`, `E`, `FR`.

These are the only way to make later disks reasonable.

Prestige currency ideas (to decide later):
- "Lifetime Clusters Moved"
- "Disks Fully Optimized"
- "Total Defrag Time"

---

## Node Philosophy (Strict Rules)

All skill tree nodes follow these rules so simulation is trivial:

1. **Only percentages and multipliers**
   - `+X%` additive to a stat
   - `xY.YY` multiplicative to a stat
   - Never "special cooldown ability", "hold for X", "one big burst", "on click chance", etc.

2. **Progressive & Stackable**
   - Multiple nodes in the same category just add their bonuses.
   - We can have 5-6 nodes that all say "+12% Manual Power" at different tiers/costs. The player feels constant improvement.

3. **No Discrete Events**
   - Everything is a continuous rate. The only player action is "click to apply current Manual rate for one tick".

4. **Diminishing but Never Dead**
   - Later nodes in a line give slightly smaller % gains or move to secondary stats so the tree stays interesting.

5. **Simulation Friendly**
   - Any point in the tree can be expressed as final values of `M`, `R`, `A`, `E`, `FR`, and file type table.
   - From there we can compute exact seconds to finish a disk if the player clicks at max rate the whole time, or 50% of the time, etc.

---

## Example Calculation Target

We want to be able to answer questions like:

- "If a player has unlocked the first 8 nodes and clicks 60% of the time, how many minutes should Disk D take?"
- "After one prestige with 2.4x global multiplier, how much faster is the start of Disk E?"

This is only possible if every upgrade is just a number on one of the primary stats.

---

## Next Documents

- `01-disk-progression.md` — exact disk sizes, hardness curves, completion thresholds, prestige triggers
- `02-manual-nodes.md` — detailed node types and example nodes for the Manual branch
- `03-auto-nodes.md`
- `04-filesystem-nodes.md`

All nodes will be written as pure +% / x multipliers on the stats defined above.

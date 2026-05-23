# Defrag Clicker — Design Documents

This folder contains the working specification for a simple, simulation-friendly clicker game about defragmenting hard drives.

## Core Principles

- Everything is percentages and multipliers (no special cooldown abilities or discrete powers).
- The game must be tunable via simulation so we know exactly how long each disk should take.
- Progression comes from bigger + stickier disks (size + hardness scaling).
- Prestige is the only way to get permanent global power that lets you tackle later disks.
- Three distinct but interconnected improvement paths: Manual, Auto, and Filesystem knowledge.

## Document Index

| File | Purpose |
|------|---------|
| `00-core-simulation-model.md` | The mathematical foundation. Defines the handful of numbers (`M`, `R`, `A`, `E`, `FR`, file type costs) that everything else modifies. |
| `01-disk-progression-and-prestige.md` | How disks scale (16GB → 32GB → 64GB..., hardness multipliers, file type mix changes, completion rules, when prestige happens, what it gives). |
| `02-manual-sweeps-node-types.md` | Extremely detailed breakdown of every category of upgrade that makes clicking the grid stronger. 6 node types with many example nodes each. |
| `03-auto-optimizer-node-types.md` | Same depth for the passive background defragger. Focus on rate, resistance, scheduling, and hybrid power. |
| `04-filesystem-intelligence-node-types.md` | The "realism and mastery" branch. File types, bad sectors, advanced techniques, major hybrid synergies, and prestige prep nodes. |

## Current Status (as of writing)

- Core model is simulation-ready.
- Disk ladder is proposed with concrete numbers.
- All three branches have been expanded into node **types** with 5–7 example nodes each, including suggested disk gates.
- No point costs or exact tuning numbers have been assigned yet (next logical step).

## Suggested Next Steps

1. Assign actual Defrag Point costs to the nodes (probably 3–5 tiers of cost per branch).
2. Write a small Python/JS simulator that takes "purchased nodes" as input and outputs "minutes to finish Disk X at Y% click uptime".
3. Decide on exact prestige triggers and rewards.
4. Define the visual + audio feedback for a Manual Sweep so it still feels juicy even though it's just rate increases.
5. Prototype the first two disks (C: and D:) in code to validate the feel.

## Philosophy Reminder

We are deliberately avoiding "cool special abilities" in favor of smooth, stackable, simulatable progression. The fantasy comes from the theme, the growing disks, the increasing realism of the problems, and the satisfying feeling of both systems getting faster together.

If something can't be expressed as a clean +% or x multiplier on one of the core stats, it probably doesn't belong in the first version.

# DEFRAG.EXE - Visual Prototype

First visual prototype of the defrag clicker using Python + pygame.

## Environment Setup (Bazzite / Immutable Fedora)

Because this is an immutable distro, we develop inside a **distrobox** container.

### One-time setup

```bash
# Enter the container we already created
distrobox enter defrag-dev

# Inside the container, install dependencies
sudo dnf install -y python3-pip python3-devel SDL2-devel SDL2_ttf-devel SDL2_image-devel gcc
pip install pygame
```

### Running the prototype

```bash
# From inside the distrobox, in the project directory
python src/main.py
```

(Or just run `./run_prototype.sh` from anywhere — it auto-detects distrobox.)

The window should appear on your host desktop.

---

## Current Prototype Features

- Classic defrag-style grid (40×18 cells)
- Three cell types: Green (good), Red (fragmented), Blue (system)
- **Click anywhere on the grid** → Manual Sweep (yellow cells animate from fragmented → good positions)
- Background auto defragger slowly cleans the drive
- Visible countdown timer (20 minutes)
- Fragmentation % display
- Basic win/lose states

This is purely visual and mechanical for now. No real skill tree or proper game systems yet — we're validating the **grid + clicking + timer** feel first.

---

## Next Visual Steps (when you're ready)

1. Better animation for moving clusters (smooth sliding, particle trails)
2. Different "data types" with distinct colors + different move difficulty
3. Simple upgrade buttons on the side (even if they just multiply numbers)
4. More retro Windows 95/98 aesthetic (borders, fonts, beeps)
5. Sound design (classic hard drive seek sounds, success chimes)

Let me know what you want to see improved or added in the next iteration of the prototype.

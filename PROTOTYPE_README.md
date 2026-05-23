# DEFRAG.EXE — Developer Notes

End-user docs are in [README.md](README.md). This file is for working on the game itself.

## Repository layout

```
src/main.py                 — the entire game (single-file pygame)
assets/                     — icon.png / icon.ico / icon.icns (generated)
docs/                       — design docs (00–04) and BUILD_PLAN.md
tests/                      — pytest suite (run via ./run_tests.sh)
tools/
    balance_sim.py          — offline balance simulator
    clear_z_check.py        — parameter-sweep probe for the final disk
    trace_z.py              — single-run trace
    make_icons.py           — regenerates assets/icon.* from a procedural design
defrag.spec                 — PyInstaller spec (one file, all three OSes)
.github/workflows/release.yml — CI matrix that builds release binaries
run_prototype.sh / run_tests.sh — convenience wrappers (auto-detect distrobox)
```

## Environment setup (Bazzite / Immutable Fedora)

Because the host is an immutable distro, we develop inside a **distrobox** container.

### One-time

```bash
distrobox create -n defrag-dev -i fedora-toolbox:40
distrobox enter defrag-dev
sudo dnf install -y python3-pip python3-devel SDL2-devel SDL2_ttf-devel SDL2_image-devel gcc
pip install pygame
```

### Running

```bash
./run_prototype.sh    # auto-detects distrobox, falls back to host python
./run_tests.sh        # same, but runs pytest
```

(Or, from inside the project directory: `python src/main.py`.)

## Building binaries locally

```bash
pip install pyinstaller
pyinstaller defrag.spec --clean --noconfirm
# Output: dist/defrag-linux-x64 (or platform equivalent)
```

The spec is cross-platform; the same file builds Linux / Windows / macOS depending on where you run it.

## Releasing

1. Bump `CFBundleShortVersionString` and `CFBundleVersion` in `defrag.spec` (macOS).
2. Commit and push.
3. Tag: `git tag v0.1.0 && git push --tags`.
4. The `release.yml` workflow builds for all three OSes and publishes a GitHub Release with all three artifacts attached.

To dry-run the workflow without cutting a release, use the **Run workflow** button on the Actions tab (uses `workflow_dispatch`).

## Tests

```bash
./run_tests.sh
```

Tests are deterministic and use `SDL_VIDEODRIVER=dummy` so they run headless in CI too (although currently we only test locally — CI runs the build, not the suite).

## Design references

- `docs/00-core-simulation-model.md` — the math foundation.
- `docs/01-disk-progression-and-prestige.md` — how disks scale and what prestige does.
- `docs/02–04-*.md` — node-type catalogues for each branch.
- `docs/BUILD_PLAN.md` — the cross-platform build plan that produced `defrag.spec` and `release.yml`.

## Visual / theme notes

- Win9x VGA-16 palette: navy `#000080`, cyan `#00FFFF`, yellow `#FFFF00`, green `#00FF00`, magenta `#FF00FF`, red `#FF0000`, classic grey `#C0C0C0`.
- Title-bar navy is the same `#000080`. Bevels: white top/left, dark-grey bottom/right.
- Fonts: SysFont fallback `"ms sans serif, tahoma, dejavu sans, arial"` — the first one that resolves wins, so the look is consistent across OSes.

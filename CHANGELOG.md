# Changelog

All notable changes to **DEFRAG.EXE** are recorded here.
The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow a `MAJOR.MINOR` scheme (semver-ish, but no patch component until needed).

## [0.1] — 2026-05-23

First public prototype release.

### Game systems
- **24 disks** to defragment, C: through Z:, with boss-hardness spikes on H, N, R, V, and Z.
- **163 skill nodes** across Manual / Click / Auto / Filesystem branches, organized as a Win95-style tree-view inspector.
- **49 legacy / prestige nodes** with milestone gates tied to your prestige count.
- **Real click-rate tracking** via a sliding window — auto-clickers contribute virtual clicks toward the same rate cap.
- **Shatter-on-clean** fragment chains: sys → media → doc → temp, with cascade physics.
- **3 save slots**, JSON on disk, autosave on disk completion and exit.

### Build / distribution
- **Cross-platform binaries** for Windows x64, Linux x64, macOS Intel, and macOS Apple Silicon.
- **Single-file `defrag.spec`** drives PyInstaller on all four targets.
- **GitHub Actions matrix** auto-builds and publishes a Release on any `v*` tag push.
- **OS-aware save paths**: `%APPDATA%` on Windows, `~/Library/Application Support` on macOS, `$XDG_DATA_HOME` on Linux.

### UI / visual
- Win95-styled chrome: beveled buttons, navy titlebars, taskbar with live system clock.
- VGA-16 palette throughout (navy background, cyan/yellow/green/magenta/red cells).
- Pause, legend, settings, end-of-session, and save/load dialogs.

### Known limitations
- No sound. The game is silent.
- No in-game tutorial beyond the legend dialog.
- Binaries are **unsigned** — first launch will trigger SmartScreen (Windows) or Gatekeeper (macOS) warnings. See [README.md](README.md#first-launch-warnings) for the bypass.
- **macOS Intel is not attached to this release.** The build pipeline still attempts an Intel build (best-effort), but the `macos-13` runner queue on free-tier GitHub Actions is too slow to gate every release on. Intel artifacts live on the workflow run's Artifacts list and may be attached in a future release.

# DEFRAG.EXE v0.1 — First public prototype

A single-file pygame defrag-themed clicker / idler, styled like Microsoft (sorry, **M1CROSOFT**) Windows 95.

## Download

| OS | File |
|---|---|
| Windows x64 | [`defrag-windows-x64.zip`](https://github.com/jtwolfe/defrag.exe/releases/download/v0.1/defrag-windows-x64.zip) |
| macOS — Apple Silicon (M1/M2/M3) | [`defrag-macos-arm64.zip`](https://github.com/jtwolfe/defrag.exe/releases/download/v0.1/defrag-macos-arm64.zip) |
| Linux x64 | [`defrag-linux-x64.tar.gz`](https://github.com/jtwolfe/defrag.exe/releases/download/v0.1/defrag-linux-x64.tar.gz) |

No install — unzip / untar and run.

> macOS Intel build is not attached to v0.1. The build pipeline still builds it (best-effort) but it isn't gating the release; it will be attached in a future release if there's demand.

## First-launch warnings

The binaries are **unsigned**. Your OS will complain on first launch.

- **Windows SmartScreen:** "Windows protected your PC" → **More info** → **Run anyway**.
- **macOS Gatekeeper:** Right-click `DEFRAG.app` → **Open** → **Open** in the dialog. Or in Terminal: `xattr -d com.apple.quarantine /path/to/DEFRAG.app`.

This is normal for hobby releases — signing requires a paid certificate (Windows) or Apple Developer enrollment (macOS).

## What's in this release

### Gameplay
- 24 disks (C: → Z:) with hardness scaling and boss-disk spikes on H, N, R, V, Z.
- 163 skill nodes across Manual / Click / Auto / Filesystem branches.
- 49-node legacy / prestige tree with milestone gates.
- Shatter-on-clean fragment cascade mechanics.
- Real click-rate tracking and auto-clickers that contribute to the same rate cap.
- 3 save slots; autosave on disk completion and exit.

### UI
- Win95-styled chrome: beveled buttons, navy titlebars, taskbar with live system clock.
- Tree-view skill inspector with right-side detail pane.
- Pause, legend, settings, end-of-session, save/load dialogs.

### Build pipeline
- Cross-platform binaries from one PyInstaller spec.
- GitHub Actions matrix: Windows x64, Linux x64, macOS Intel, macOS Apple Silicon.

## Known limitations

- No sound.
- No in-game tutorial beyond the legend dialog.
- Save files live in OS-conventional locations: `%APPDATA%\defrag.exe\` on Windows, `~/Library/Application Support/defrag.exe/` on macOS, `$XDG_DATA_HOME/defrag.exe/` on Linux.

## License

PolyForm Noncommercial 1.0.0 — free to play, study, modify, and share modifications for noncommercial purposes. Commercial rights reserved. See [LICENSE](https://github.com/jtwolfe/defrag.exe/blob/main/LICENSE).

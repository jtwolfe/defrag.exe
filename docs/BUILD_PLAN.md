# DEFRAG.EXE — Cross-Platform Build Plan

This document is the plan for turning the current `src/main.py` source tree into single-file downloadable binaries for **Windows (x64)**, **macOS (Universal2 — Intel + Apple Silicon)**, and **Linux (x64)**, distributed via GitHub Releases.

Scope: build pipeline only. No gameplay changes.

---

## 1. Goals

1. End user downloads one file from the GitHub **Releases** page for their OS and double-clicks to play. No Python install, no `pip`, no terminal.
2. Saves persist across upgrades (same save directory, regardless of binary version).
3. Builds happen automatically on `git tag` push (e.g. `v0.1.0`). No manual local building required.
4. The build is reproducible from a clean checkout — anyone with a GitHub fork can produce their own binaries.

Out of scope (for v1):
- Code signing on Windows (requires a paid certificate)
- Apple notarization (requires Apple Developer Program enrollment — $99/yr)
- Linux `.deb`/`.rpm`/Flatpak packaging
- Installers (NSIS, .msi, .dmg, .AppImage). v1 ships **bare executables / app bundles in a zip**.

We can revisit signing/installers in a v2 pass once the binary pipeline is proven.

---

## 2. Packaging Tool: PyInstaller

**Choice:** [PyInstaller](https://pyinstaller.org/) ≥ 6.x.

### Why PyInstaller
- It is the most mature pygame-compatible bundler. The pygame project's own examples and most community releases use it.
- It supports `--onefile` mode, producing a single executable that self-extracts to a temp dir at runtime.
- It handles SDL2 / SDL2_ttf / SDL2_mixer DLL bundling correctly out of the box.
- Cross-platform spec file: one `defrag.spec` works on all three OSes (with small `if sys.platform` branches if needed).

### Alternatives considered and rejected for v1
| Tool | Why not |
|------|---------|
| **Nuitka** | Compiles to C — smaller and faster binaries, but slower build, harder pygame data-file story, more sensitive to dynamic imports. Worth re-evaluating in v2. |
| **PyOxidizer** | Embeds Python statically. Strong tool, but pygame + SDL bundling is poorly documented and requires custom shims. |
| **BeeWare Briefcase** | App-store-shaped output (`.app`, `.msi`, AppImage). Heavier; aimed at full app packaging rather than "one binary to download". Good v2 candidate if we want installers. |
| **py2app / py2exe** | OS-specific. Would need two separate pipelines. PyInstaller covers all three. |

---

## 3. Build Matrix

GitHub Actions matrix with three runners:

| OS runner | Output artifact | Save dir at runtime |
|-----------|-----------------|----------------------|
| `windows-latest` (x64) | `defrag-windows-x64.zip` containing `DEFRAG.EXE.exe` | `%APPDATA%\defrag.exe\` |
| `macos-13` (Intel x86_64) | `defrag-macos-intel.zip` containing `DEFRAG.app` | `~/Library/Application Support/defrag.exe/` |
| `macos-14` (Apple Silicon arm64) | `defrag-macos-arm64.zip` containing `DEFRAG.app` | `~/Library/Application Support/defrag.exe/` |
| `ubuntu-22.04` (x64) | `defrag-linux-x64.tar.gz` containing `defrag-linux-x64` executable | `$XDG_DATA_HOME/defrag.exe/` or `~/.local/share/defrag.exe/` |

**Why ubuntu-22.04 and not -latest:** GLIBC compatibility. Binaries built on newer Ubuntu fail on older distros because they dynamically link against a newer `libc`. 22.04 (GLIBC 2.35) is a good compatibility floor that still covers Fedora 36+, Debian 12+, Arch, recent Mint, etc.

**Why two Mac jobs and not Universal2:** pygame wheels on PyPI are arch-specific (`macosx_11_0_arm64` and `macosx_10_9_x86_64` — not fat binaries). PyInstaller's `target_arch='universal2'` requires every bundled `.so` to contain both architectures and errors out when it sees a thin pygame wheel. The clean fix is two artifacts: `macos-13` runner builds the Intel zip, `macos-14` runner builds the Apple Silicon zip. Users pick the one matching their Mac.

---

## 4. The `.spec` File

We will commit a single `defrag.spec` at the repo root. Key contents:

```python
# defrag.spec (sketch — actual values pinned during implementation)
import sys
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    datas=collect_data_files('pygame'),   # pygame's bundled fonts/data
    hiddenimports=[],                     # add any if PyInstaller misses imports
    hookspath=[],
    excludes=['tkinter', 'unittest', 'pytest'],   # shrink the bundle
)

pyz = PYZ(a.pure, a.zipped_data)

# Per-platform exe naming
exe_name = {
    'win32':  'DEFRAG.EXE',
    'darwin': 'defrag',
    'linux':  'defrag-linux-x64',
}[sys.platform]

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas,
    name=exe_name,
    console=False,                # no terminal window on Windows
    onefile=True,
    icon='assets/icon.ico' if sys.platform == 'win32' else
         'assets/icon.icns' if sys.platform == 'darwin' else None,
)

# macOS app bundle wrapping
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='DEFRAG.app',
        icon='assets/icon.icns',
        bundle_identifier='com.jtwolfe.defrag',
        info_plist={'NSHighResolutionCapable': 'True'},
    )
```

**Open questions when we implement:**
- Does `collect_data_files('pygame')` pull everything we need, or do we need to also `collect_dynamic_libs('pygame')`? Verify by running the produced binary on a clean VM.
- We need to create `assets/icon.ico`, `icon.icns`, and (optionally) `icon.png` before this works. The `assets/` directory exists in the repo but is currently empty.

---

## 5. GitHub Actions Workflow

Single file: `.github/workflows/release.yml`. Triggers on tags matching `v*`.

```yaml
name: Build release binaries

on:
  push:
    tags: ['v*']
  workflow_dispatch:   # allow manual builds for testing

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: ubuntu-22.04
            artifact: defrag-linux-x64.tar.gz
          - os: windows-latest
            artifact: defrag-windows-x64.zip
          - os: macos-14
            artifact: defrag-macos.zip
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install pygame pyinstaller
      - run: pyinstaller defrag.spec --clean --noconfirm
      # Per-OS packaging steps (zip/tar) — see below
      - uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact }}
          path: dist/${{ matrix.artifact }}

  release:
    needs: build
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/v')
    steps:
      - uses: actions/download-artifact@v4
      - uses: softprops/action-gh-release@v2
        with:
          files: |
            defrag-linux-x64.tar.gz/*
            defrag-windows-x64.zip/*
            defrag-macos.zip/*
```

**Per-OS packaging** (sketched separately for clarity):
- Linux: `tar -czf dist/defrag-linux-x64.tar.gz -C dist defrag-linux-x64`
- Windows: PowerShell `Compress-Archive dist/DEFRAG.EXE.exe dist/defrag-windows-x64.zip`
- macOS: `cd dist && zip -r defrag-macos.zip DEFRAG.app`

---

## 6. Save File Path Compatibility

The game currently writes saves to a directory under `XDG_DATA_HOME` (Linux convention). For packaged builds, we want the save path to follow each OS's conventions so binaries can find existing saves regardless of how the game was launched.

**Action:** add a small `save_dir()` helper in `src/main.py` (replacing the current hardcoded XDG path logic):

```python
def save_dir():
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
    elif sys.platform == 'darwin':
        base = os.path.expanduser('~/Library/Application Support')
    else:  # linux & friends
        base = os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')
    return os.path.join(base, 'defrag.exe')
```

This is a small surgical change to existing code, not a refactor — but it must happen **before** we ship binaries so first-launch saves land in the right place per OS.

---

## 7. Versioning & Tagging

- Use semver: `v0.1.0`, `v0.2.0`, etc.
- Embed the version string at build time via `PyInstaller`'s `--version-file` (Windows) or just a `VERSION` constant in `src/main.py` updated by hand at tag time. Initially: manual constant + git tag must match.
- `git tag v0.1.0 && git push --tags` triggers the workflow.

A pre-release sanity tag (`v0.1.0-test`) can be used to dry-run the full pipeline before announcing.

---

## 8. Risks / Things That Often Break

1. **pygame DLL bundling on Windows.** PyInstaller usually picks up SDL2.dll, but missing `SDL2_ttf.dll` is a classic failure. Mitigation: smoke-test the produced binary on a clean Windows VM with no Python installed.
2. **macOS Gatekeeper.** Unsigned `.app` will trigger "DEFRAG.app is damaged and can't be opened" on first launch. Users need to right-click → Open, or `xattr -d com.apple.quarantine DEFRAG.app`. Document this in the README. v2 fix: notarize.
3. **Windows SmartScreen.** Unsigned `.exe` shows "Windows protected your PC" warning. Users click "More info" → "Run anyway". Document in README. v2 fix: code-signing certificate.
4. **Linux GLIBC mismatch.** Mitigated by building on ubuntu-22.04 (older GLIBC). If we want to cover RHEL/CentOS, we'd need to build on a manylinux container (significantly more work).
5. **Onefile startup lag.** `--onefile` self-extracts to a temp dir on every launch — adds 1–3s of pygame splash silence. Acceptable for a hobby game. If irritating, switch to `--onedir` and ship a folder instead.
6. **Asset files.** Currently `assets/` is empty. Before tagging v0.1.0 we need at minimum: `icon.ico` (Windows), `icon.icns` (macOS). Linux icons are optional. These need to be generated from a single source PNG/SVG.

---

## 9. Implementation Order

When you give the green light to build this out, the order is:

1. **Add OS-aware `save_dir()`** in `src/main.py`. Verify saves still load on Linux.
2. **Generate icon files** (icon.png → icon.ico, icon.icns). Probably a 5-minute job with ImageMagick + `iconutil`.
3. **Write `defrag.spec`** and verify a local `pyinstaller defrag.spec` produces a working binary on Linux (the host platform).
4. **Smoke test** the local binary: clean shell, no venv active, no pygame on PATH — does it launch?
5. **Write `.github/workflows/release.yml`** with the three-OS matrix.
6. **Trigger via `workflow_dispatch`** (manual run) first — verify all three OSes build cleanly before tagging anything public.
7. **Download each artifact** and smoke-test on a real machine (or VM) for each OS. Especially Windows and macOS.
8. **Tag `v0.1.0`** once all three work. The workflow auto-creates the GitHub Release.
9. **Update `PROTOTYPE_README.md`** with: "Download the latest release [here] — no install needed."

Estimated time, conservatively: 4–8 hours of work, mostly spent on iteration cycles around step 6 (CI runs are slow and macOS quirks burn time).

---

## 10. Open Questions for You

These need a decision before I start implementing:

1. **macOS strategy:** Universal2 single binary, or two separate Intel + ARM artifacts? (Universal2 is cleaner for users; two artifacts is more robust if Universal2 builds break.)
2. **Icon source:** do you want to design one, or should I generate a placeholder (e.g. a stylized "D:" or floppy disk) from a simple SVG?
3. **Versioning:** start at `v0.1.0`, or call it `v1.0.0` since it's already feature-complete?
4. **README rewrite:** the current `PROTOTYPE_README.md` is dev-oriented. Do you want me to write a separate end-user `README.md` (which GitHub displays on the repo page) at the same time as the build pipeline lands?

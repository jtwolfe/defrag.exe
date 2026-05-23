# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for DEFRAG.EXE.

Single spec used by all three OS build jobs in .github/workflows/release.yml.
Per-platform branches handle exe name, icon format, and the macOS .app bundle.

Usage:
    pyinstaller defrag.spec --clean --noconfirm
"""
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# pygame ships with bundled fonts + SDL native libs. Pull both in explicitly.
pygame_datas = collect_data_files('pygame')
pygame_bins  = collect_dynamic_libs('pygame')

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=pygame_bins,
    datas=pygame_datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pytest', 'numpy', 'PIL'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Per-OS naming + icon. Keep the launched binary visibly themed.
if sys.platform == 'win32':
    exe_name = 'DEFRAG.EXE'
    icon_path = 'assets/icon.ico'
elif sys.platform == 'darwin':
    exe_name = 'defrag'
    icon_path = 'assets/icon.icns'
else:
    exe_name = 'defrag-linux-x64'
    icon_path = None  # no native Linux icon format; window-manager icon comes from .desktop

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,             # UPX can corrupt SDL DLLs on Windows
    runtime_tmpdir=None,
    console=False,         # no terminal window on Windows
    disable_windowed_traceback=False,
    target_arch=None,    # use host arch — pygame wheels aren't universal2,
                         # so we build per-arch on macos-13 (Intel) and macos-14 (ARM)
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

# macOS: wrap the executable in a .app bundle.
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='DEFRAG.app',
        icon='assets/icon.icns',
        bundle_identifier='com.jtwolfe.defrag',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'CFBundleDisplayName': 'DEFRAG.EXE',
            'CFBundleShortVersionString': '0.1',
            'CFBundleVersion': '0.1',
            'NSHumanReadableCopyright': 'Free for personal use.',
        },
    )

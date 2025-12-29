# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Video Subtitle Toolkit
Build with: pyinstaller build.spec
"""

import sys
from pathlib import Path

block_cipher = None

# Get the directory containing the spec file
SPEC_DIR = Path(SPECPATH)

# Main script
main_script = str(SPEC_DIR / 'gui.py')

# Additional scripts to bundle as data
scripts_to_bundle = [
    'run_canary.py',
    'srt.py',
    'text_to_srt.py',
    'video_speed_adjuster_v3.py',
    'menu.py',
]

datas = [(str(SPEC_DIR / s), '.') for s in scripts_to_bundle if (SPEC_DIR / s).exists()]

a = Analysis(
    [main_script],
    pathex=[str(SPEC_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
        'queue',
        'threading',
        'subprocess',
        'pathlib',
        'datetime',
        're',
        'shutil',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy ML libraries from the base build
        'torch',
        'tensorflow',
        'numpy',
        'pandas',
        'matplotlib',
        'scipy',
        'nemo',
        'nemo_toolkit',
        'soundfile',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='VideoSubtitleToolkit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one
)

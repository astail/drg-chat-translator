# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller のビルド定義。"""

import os

block_cipher = None

datas = [
    ("bridge/glossary.json", "."),
    ("settings.example.ini", "."),
    ("mod/DRGTranslate", "mod/DRGTranslate"),
]

hiddenimports = [
    "anthropic",
    "openai",
]

a = Analysis(
    ["bridge/drg_bridge.py"],
    pathex=["bridge"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "numpy", "pandas", "matplotlib", "scipy", "PIL",
        "pytest", "setuptools", "pip",
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
    name="DRGTranslate",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

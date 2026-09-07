# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Furniture Bill desktop app (PyInstaller >= 6).

Build:  build_exe.bat
Output: dist/FurnitureBill/
"""
from pathlib import Path

a = Analysis(
    ['run.py'],
    pathex=[str(Path.cwd())],
    binaries=[],
    datas=[
        # Bundle the runtime assets (login background etc.)
        ('app/resources', 'app/resources'),
    ],
    hiddenimports=[
        # Ed25519 verification + any PDF/xlsx helpers the hooks may miss
        'cryptography.hazmat.primitives.asymmetric.ed25519',
        'cryptography.hazmat.primitives.serialization',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'pytest',
        'PySide6.QtWebEngineCore',
        'license_server',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FurnitureBill',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    a.zipfiles,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FurnitureBill',
)
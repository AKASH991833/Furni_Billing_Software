# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Single-File Standalone Portable EXE.

Builds a single, standalone .exe in dist/FurnitureBill_Portable.exe that
runs directly on double-click with no installation required.
"""
from pathlib import Path

a = Analysis(
    ['run.py'],
    pathex=[str(Path.cwd())],
    binaries=[],
    datas=[
        ('app/resources', 'app/resources'),
    ],
    hiddenimports=[
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtPrintSupport',
        'PySide6.QtCharts',
        'cryptography.hazmat.primitives.asymmetric.ed25519',
        'cryptography.hazmat.primitives.serialization',
        'sqlalchemy.dialects.sqlite',
        'qrcode',
        'PIL',
        'PIL.Image',
        'openpyxl',
        'openpyxl.chart',
        'openpyxl.styles',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'pytest',
        'license_server',
        'psycopg2',
        'numpy',
        'PySide6.QtBluetooth',
        'PySide6.QtSensors',
        'PySide6.QtNfc',
        'PySide6.QtPositioning',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtSpatialAudio',
        'PySide6.QtTest',
        'PySide6.QtDesigner',
        'PySide6.QtHelp',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FurnitureBill_Portable',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app/resources/icons/app.ico',
)

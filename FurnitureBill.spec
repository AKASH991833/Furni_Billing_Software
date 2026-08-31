# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the Furniture Bill standalone Windows app."""
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# Include PySide6 QtWebEngine resources (QtPdf, WebEngineCore, Chromium)
for pkg in (
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtCharts",
    "PySide6.QtPrintSupport",
):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += [
    "app.main",
    "app.ui.main_window",
    "app.ui.pages.dashboard_page",
    "app.ui.pages.customers_page",
    "app.ui.pages.invoices_page",
    "app.ui.pages.invoice_editor",
    "app.ui.pages.reports_page",
    "app.ui.pages.settings_page",
    "app.ui.pages.payment_dialog",
    "app.ui.pages.base_page",
    "app.ui.widgets.sidebar",
    "app.ui.widgets.header",
    "app.ui.widgets.common",
    "app.services.business_service",
    "app.services.customer_service",
    "app.services.invoice_service",
    "app.services.catalog_service",
    "app.services.dashboard_service",
    "app.services.report_service",
    "app.services.payment_service",
    "app.services.backup_service",
    "app.services.whatsapp_service",
    "app.pdf.html_template",
    "app.pdf.pdf_service",
    "app.database.database",
    "app.database.seed",
    "app.models.models",
    "app.utils.calculations",
    "app.utils.paths",
]

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FurnitureBill",
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
    icon="app/resources/icons/app.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FurnitureBill",
)

# One-folder build. Use `--onefile` build command if a single .exe is preferred.

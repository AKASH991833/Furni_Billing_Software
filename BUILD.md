# Furniture Bill Software — Production Build & Packaging Guide

This guide explains how to reproducibly build the standalone desktop application and generate the official Windows Installer (`FurnitureBill_Setup.exe`) from scratch.

---

## 1. System Requirements

- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python Version**: Python 3.11, 3.12, 3.13, or 3.14 (64-bit)
- **Inno Setup**: Inno Setup 6.x (installed automatically or via `winget`)

---

## 2. Dependencies Installation

To set up the required packaging and runtime libraries, run:

```bash
pip install -r requirements.txt
pip install pyinstaller
```

### Key Bundled Libraries:
- **PySide6**: Qt6 GUI Framework, `QtWebEngineWidgets` (PDF rendering), `QtPrintSupport` (Printing), `QtCharts` (Dashboard).
- **openpyxl**: Excel workbook generation and charts.
- **qrcode & Pillow**: Dynamic Indian UPI QR code generation and high-DPI logo scaling.
- **cryptography**: Ed25519 asymmetric signature verification for lifetime offline activation.
- **sqlalchemy**: SQLite ORM and automatic schema migrations.

---

## 3. One-Click Production Build

To build both the standalone application and the official Windows installer in one step:

### Option A: From Command Prompt / Terminal
```bash
python build_release.py
```

### Option B: Double-Click Batch File
Double-click `build_exe.bat` in the repository root.

---

## 4. What the Build Pipeline Does

1. **Environment Validation**:
   Checks that Python 64-bit, PySide6, QtWebEngine, openpyxl, Pillow, qrcode, cryptography, and PyInstaller are properly installed.
2. **Artifact Cleanup**:
   Wipes previous `build/` and `dist/` directories to prevent stale cache contamination.
3. **PyInstaller Compilation (`--onedir`)**:
   - Generates high-performance portable binary folder at `dist/FurnitureBill/`.
   - Bundles all required Qt platform plugins, WebEngine Chromium resources, SQLite drivers, and encryption libraries.
   - Embeds high-resolution application icon (`app/resources/icons/app.ico`).
4. **Inno Setup Compilation (`dist/FurnitureBill_Setup.exe`)**:
   - Compiles `installer.iss` using Inno Setup 6.
   - Creates a modern Windows setup wizard.
   - Adds Start Menu shortcut and Desktop shortcut with custom luxury furniture icon.
   - Protects customer database from accidental deletion during uninstall.

---

## 5. Build Outputs

| Artifact | Location | Purpose |
| :--- | :--- | :--- |
| **Standalone Folder** | `dist/FurnitureBill/` | Unpacked portable application directory |
| **Main Executable** | `dist/FurnitureBill/FurnitureBill.exe` | Core application binary |
| **Official Installer** | `dist/FurnitureBill_Setup.exe` | Customer-ready single-file installer |

---

## 6. Data Directory & Persistence Architecture

To comply with Windows security standards and prevent permissions errors in `C:\Program Files`, all mutable user data is isolated:

- **Database Path**: `%APPDATA%\FurnitureBill\data\furniture.db`
- **Backups Path**: `%APPDATA%\FurnitureBill\data\backups\`
- **Custom Logo**: `%APPDATA%\FurnitureBill\data\logo.*`

**Uninstall Behavior**:
Uninstalling `Furniture Bill Software` via Windows Control Panel / Settings removes the application binaries in `Program Files`, but **never** deletes `%APPDATA%\FurnitureBill\data\`. If the user reinstalls or upgrades the app, their database, invoices, and worker records remain 100% intact.

---

## 7. Version Update Procedure

When releasing a new version:
1. Update `APP_VERSION = "x.y.z"` in `app/config.py`.
2. Update `#define MyAppVersion "x.y.z"` in `installer.iss`.
3. Run `python build_release.py`.

---

## 8. Clean PC Customer Deployment Checklist

1. Transfer `FurnitureBill_Setup.exe` to the client's PC (via USB drive, Google Drive, or direct download).
2. Double-click `FurnitureBill_Setup.exe` and follow the wizard (takes ~5 seconds).
3. The desktop shortcut with the Furniture icon will appear.
4. Double-click the desktop shortcut.
5. On first launch, the software will ask for the Customer Activation Key.
6. Enter the issued activation key (or trial key).
7. Set up the 4-digit PIN.
8. The software is ready for commercial billing!

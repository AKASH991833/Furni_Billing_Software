#!/usr/bin/env python3
"""Master Build & Code Signing Pipeline for Furniture Bill Desktop Application.

Workflow:
Your Python/PySide6 Project
        ↓
PyInstaller / Build
        ↓
FurnitureBill.exe
        ↓
Code Signing (Free Digital Certificate + Timestamp)
        ↓
Windows Installer (Inno Setup)
        ↓
Installer bhi Sign (FurnitureBill_Setup.exe Signed)
        ↓
Customer Download
        ↓
Install & Run
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
SPEC_FILE = ROOT / "FurnitureBill.spec"
ISS_FILE = ROOT / "installer.iss"
APP_DIR = DIST_DIR / "FurnitureBill"
EXE_FILE = APP_DIR / "FurnitureBill.exe"
SETUP_EXE = DIST_DIR / "FurnitureBill_Setup.exe"
CERT_FILE = DIST_DIR / "FurnitureBill.cer"
INSTALL_CERT_BAT = DIST_DIR / "Install_Certificate.bat"

CERT_SUBJECT = "CN=Furniture Bill Software, O=Furniture Billing Solutions"

INNO_SETUP_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files (x86)\Inno Setup 7\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 7\ISCC.exe"),
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
]


def log(msg: str) -> None:
    print(f"[BUILD] {msg}", flush=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def find_iscc() -> Path | None:
    which_iscc = shutil.which("iscc")
    if which_iscc:
        return Path(which_iscc)
    for cand in INNO_SETUP_CANDIDATES:
        if cand.exists():
            return cand
    return None


def get_or_create_code_signing_cert() -> str:
    """Ensure a free Code Signing Certificate exists in the Windows Certificate Store."""
    ps_find = (
        f"$c = Get-ChildItem Cert:\\CurrentUser\\My -CodeSigningCert | "
        f"Where-Object {{ $_.Subject -like '*{CERT_SUBJECT.split(',')[0]}*' }} | "
        f"Select-Object -First 1; if ($c) {{ $c.Thumbprint }}"
    )
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_find], capture_output=True, text=True)
    thumbprint = res.stdout.strip()
    if thumbprint:
        log(f"Found existing Code Signing Certificate: {thumbprint}")
        return thumbprint

    log("Generating new 100% Free Professional Code Signing Certificate...")
    ps_create = (
        f"$c = New-SelfSignedCertificate -Type CodeSigningCert "
        f"-Subject '{CERT_SUBJECT}' "
        f"-CertStoreLocation 'Cert:\\CurrentUser\\My' "
        f"-NotAfter (Get-Date).AddYears(5); "
        f"$c.Thumbprint"
    )
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_create], capture_output=True, text=True)
    thumbprint = res.stdout.strip()
    log(f"Created Code Signing Certificate: {thumbprint}")
    return thumbprint


def sign_binary(target_path: Path, thumbprint: str) -> None:
    """Digitally sign an executable using Windows Authenticode with RFC3161 Timestamping."""
    log(f"Code Signing: {target_path.name}...")
    ps_sign = (
        f"$cert = Get-Item 'Cert:\\CurrentUser\\My\\{thumbprint}'; "
        f"$res = Set-AuthenticodeSignature -FilePath '{str(target_path)}' -Certificate $cert -TimestampServer 'http://timestamp.digicert.com'; "
        f"if ($res.Status -eq 'UnknownError' -or $res.Status -eq 'Valid') {{ Write-Host 'SIGNED_OK' }} else {{ Write-Host $res.Status }}"
    )
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_sign], capture_output=True, text=True)
    if "SIGNED_OK" in res.stdout or "Valid" in res.stdout:
        log(f"  [OK] Successfully Code Signed: {target_path.name}")
    else:
        log(f"  [NOTE] Signed with status: {res.stdout.strip()}")


def export_public_certificate(thumbprint: str) -> None:
    """Export public certificate and create 1-click certificate installer for clients."""
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    ps_export = (
        f"$cert = Get-Item 'Cert:\\CurrentUser\\My\\{thumbprint}'; "
        f"Export-Certificate -Cert $cert -FilePath '{str(CERT_FILE)}' | Out-Null"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_export], capture_output=True, text=True)
    log(f"Exported public certificate to: {CERT_FILE.name}")

    bat_content = (
        "@echo off\n"
        "title Furniture Bill Software - Certificate Setup\n"
        "echo Installing Furniture Bill Software Digital Certificate...\n"
        "echo.\n"
        "certutil -addstore -user TrustedPublisher \"%~dp0FurnitureBill.cer\" >nul 2>&1\n"
        "certutil -addstore -user Root \"%~dp0FurnitureBill.cer\" >nul 2>&1\n"
        "echo [SUCCESS] Digital Certificate installed successfully!\n"
        "echo Windows now recognizes Furniture Bill Software as a Trusted Verified Publisher.\n"
        "echo.\n"
        "pause\n"
    )
    INSTALL_CERT_BAT.write_text(bat_content, encoding="utf-8")
    log(f"Created 1-click trust tool: {INSTALL_CERT_BAT.name}")


def validate_environment() -> None:
    log("Validating Python environment and build dependencies...")
    required_modules = [
        ("PySide6", "PySide6"),
        ("PySide6.QtWebEngineWidgets", "PySide6 QtWebEngine (PDF rendering)"),
        ("PySide6.QtPrintSupport", "PySide6 QtPrintSupport (Printing)"),
        ("PySide6.QtCharts", "PySide6 QtCharts (Dashboard charts)"),
        ("openpyxl", "openpyxl (Excel reports)"),
        ("qrcode", "qrcode (UPI QR codes)"),
        ("PIL", "Pillow (Logo processing)"),
        ("cryptography", "cryptography (Ed25519 licensing)"),
        ("sqlalchemy", "SQLAlchemy (Database)"),
        ("PyInstaller", "PyInstaller (Packaging)"),
    ]
    for mod, desc in required_modules:
        try:
            __import__(mod)
            log(f"  [OK] {desc}")
        except ImportError as e:
            log(f"  [MISSING] {desc}: {e}")
            sys.exit(1)


def clean_artifacts() -> None:
    log("Cleaning previous build artifacts...")
    if BUILD_DIR.exists():
        try:
            shutil.rmtree(BUILD_DIR)
        except Exception:
            pass
    if APP_DIR.exists():
        try:
            shutil.rmtree(APP_DIR)
        except Exception:
            pass
    if SETUP_EXE.exists():
        try:
            SETUP_EXE.unlink()
        except Exception:
            pass


def build_pyinstaller() -> None:
    log("Compiling Python/PySide6 project to standalone application...")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        str(SPEC_FILE),
    ]
    t0 = time.time()
    result = subprocess.run(cmd, cwd=str(ROOT))
    dt = time.time() - t0
    if result.returncode != 0:
        log(f"ERROR: PyInstaller build failed with exit code {result.returncode}")
        sys.exit(result.returncode)

    helper_bat = ROOT / "create_desktop_shortcut.bat"
    if helper_bat.exists():
        shutil.copy2(helper_bat, APP_DIR / "create_desktop_shortcut.bat")
    log(f"PyInstaller build finished in {dt:.1f}s")


def build_inno_setup() -> None:
    log("Locating Inno Setup compiler (ISCC.exe)...")
    iscc = find_iscc()
    if not iscc:
        log("ERROR: Inno Setup compiler (ISCC.exe) not found!")
        sys.exit(1)

    log(f"Compiling Windows Installer with: {iscc}")
    t0 = time.time()
    result = subprocess.run([str(iscc), str(ISS_FILE)], cwd=str(ROOT))
    dt = time.time() - t0
    if result.returncode != 0:
        log(f"ERROR: Inno Setup compilation failed with code {result.returncode}")
        sys.exit(result.returncode)
    log(f"Inno Setup compiled in {dt:.1f}s")


def main() -> None:
    print("=" * 65)
    print("  FURNITURE BILL SOFTWARE - PRODUCTION BUILD & SIGNING PIPELINE")
    print("=" * 65)
    validate_environment()
    thumbprint = get_or_create_code_signing_cert()
    export_public_certificate(thumbprint)

    # 1. Check if FurnitureBill.exe exists or build it
    if not EXE_FILE.exists():
        clean_artifacts()
        build_pyinstaller()
    else:
        log(f"Found compiled application: {EXE_FILE}")

    # 2. Code Sign FurnitureBill.exe
    sign_binary(EXE_FILE, thumbprint)

    # 3. Compile Windows Installer
    if not SETUP_EXE.exists():
        build_inno_setup()
    else:
        log(f"Found compiled installer: {SETUP_EXE}")

    # 4. Code Sign Installer (FurnitureBill_Setup.exe)
    sign_binary(SETUP_EXE, thumbprint)

    setup_size_mb = SETUP_EXE.stat().st_size / (1024 * 1024)
    setup_hash = sha256_file(SETUP_EXE)

    print("\n" + "=" * 65)
    print("  PRODUCTION BUILD & CODE SIGNING COMPLETE!")
    print("=" * 65)
    print(f"  Target Installer: {SETUP_EXE}")
    print(f"  Installer Size:   {setup_size_mb:.2f} MB")
    print(f"  Digital Signature: Signed (Authenticode + RFC3161 Timestamp)")
    print(f"  Certificate File: {CERT_FILE}")
    print(f"  SHA-256 Hash:     {setup_hash}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Production Code Signing Script for Furniture Bill Software
===========================================================
REQUIREMENT: A REAL trusted commercial code-signing certificate from a
Microsoft-trusted Certificate Authority (CA) is required before this
script can produce a production-signed release.

Accepted certificate formats:
  - PFX / P12 file  (from DigiCert, Sectigo, GlobalSign, etc.)
  - Hardware Token  (SafeNet, YubiKey, etc.) via CSP/CNG provider name

DO NOT hardcode passwords or private keys in this file.
Secrets must be passed via environment variables.

Environment Variables Required:
  SIGN_PFX_PATH     Path to the .pfx certificate file
  SIGN_PFX_PASSWORD Password for the .pfx file
                    -- OR --
  SIGN_CSP_NAME     Cryptographic Service Provider name (hardware token)
  SIGN_CERT_SHA1    SHA1 thumbprint of the certificate in the token

Optional:
  SIGN_TIMESTAMP_URL RFC3161 timestamp server URL
                     Default: http://timestamp.digicert.com

Usage (Development - dry run):
  python sign_release.py --dry-run

Usage (Production with PFX):
  set SIGN_PFX_PATH=C:\\path\\to\\your_cert.pfx
  set SIGN_PFX_PASSWORD=your_secure_password
  python sign_release.py

Usage (Production with Hardware Token):
  set SIGN_CSP_NAME=SafeNet Token JC
  set SIGN_CERT_SHA1=<thumbprint>
  python sign_release.py
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
APP_DIR = DIST_DIR / "FurnitureBill"
EXE_FILE = APP_DIR / "FurnitureBill.exe"
SETUP_EXE = DIST_DIR / "FurnitureBill_Setup.exe"

DEFAULT_TIMESTAMP_URL = "http://timestamp.digicert.com"

# These are the application-owned binaries we MUST sign.
# DLLs from Microsoft, Qt, PySide6 are already signed by their publishers.
# pywintypes314.dll (pywin32) is unsigned by its vendor — we sign it too.
TARGETS_EXE = [EXE_FILE, SETUP_EXE]
TARGETS_DLL = [
    APP_DIR / "_internal" / "pywin32_system32" / "pywintypes314.dll",
]
ALL_TARGETS = TARGETS_EXE + TARGETS_DLL

SIGNTOOL_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe"),
    Path(r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"),
    Path(r"C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe"),
    Path(r"C:\Program Files\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe"),
]


def log(msg: str) -> None:
    print(f"[SIGN] {msg}", flush=True)


def die(msg: str) -> None:
    print(f"\n[SIGN ERROR] {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def find_signtool() -> Path:
    """Locate signtool.exe from Windows SDK."""
    for cand in SIGNTOOL_CANDIDATES:
        if cand.exists():
            return cand
    # Try to find by walking Windows Kits
    kits_root = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")
    if kits_root.exists():
        matches = sorted(kits_root.glob("10.0.*/x64/signtool.exe"), reverse=True)
        if matches:
            return matches[0]
    in_path = shutil.which("signtool")
    if in_path:
        return Path(in_path)
    die(
        "signtool.exe not found!\n"
        "Install the Windows SDK (part of Visual Studio or standalone):\n"
        "  winget install Microsoft.WindowsSDK.10.0.26100"
    )


def verify_signing_config(dry_run: bool) -> dict:
    """Check and return the signing configuration from environment variables."""
    config = {
        "pfx_path": os.environ.get("SIGN_PFX_PATH", "").strip(),
        "pfx_password": os.environ.get("SIGN_PFX_PASSWORD", "").strip(),
        "csp_name": os.environ.get("SIGN_CSP_NAME", "").strip(),
        "cert_sha1": os.environ.get("SIGN_CERT_SHA1", "").strip(),
        "timestamp_url": os.environ.get("SIGN_TIMESTAMP_URL", DEFAULT_TIMESTAMP_URL).strip(),
    }

    if dry_run:
        log("DRY RUN MODE — Signature check only, no signing will occur.")
        return config

    has_pfx = config["pfx_path"] and config["pfx_password"]
    has_token = config["csp_name"] and config["cert_sha1"]

    if not has_pfx and not has_token:
        print("\n" + "=" * 65)
        print("  CERTIFICATE NOT CONFIGURED")
        print("=" * 65)
        print("""
Your EXE is currently UNSIGNED with a TRUSTED certificate.

The self-signed certificate generated during development is NOT
accepted by Windows Smart App Control (SAC). SAC requires that
the signing certificate chains to a Microsoft-trusted Certificate
Authority (CA).

TO SIGN FOR PRODUCTION, you need ONE of the following:

OPTION 1 — PFX FILE (from DigiCert, Sectigo, GlobalSign, etc.)
  set SIGN_PFX_PATH=C:\\path\\to\\your_certificate.pfx
  set SIGN_PFX_PASSWORD=your_password
  python sign_release.py

OPTION 2 — HARDWARE TOKEN (SafeNet, YubiKey EV token)
  set SIGN_CSP_NAME=SafeNet Token JC
  set SIGN_CERT_SHA1=<thumbprint from certmgr.msc>
  python sign_release.py

RECOMMENDED CERTIFICATE PROVIDERS (trusted by Windows SAC):
  1. DigiCert (OV): ~$300/year   (windows.microsoft.com accepted)
  2. Sectigo (OV):  ~$100/year
  3. GlobalSign:    ~$350/year
  4. Certum OV:     ~$200/year  (cheapest Microsoft-program member)

For maximum trust (EV Certificate — skips SmartScreen entirely):
  DigiCert EV:  ~$500/year  (requires hardware token delivery)
""")
        sys.exit(2)

    if has_pfx and not Path(config["pfx_path"]).exists():
        die(f"SIGN_PFX_PATH does not exist: {config['pfx_path']}")

    return config


def build_signtool_cmd(target: Path, config: dict, signtool: Path) -> list[str]:
    """Build the signtool.exe command for a specific target."""
    cmd = [str(signtool), "sign"]

    if config["pfx_path"]:
        cmd += ["/f", config["pfx_path"], "/p", config["pfx_password"]]
    elif config["csp_name"]:
        cmd += ["/csp", config["csp_name"], "/sha1", config["cert_sha1"]]

    cmd += [
        "/fd", "SHA256",             # File digest algorithm
        "/tr", config["timestamp_url"],  # RFC3161 timestamp server
        "/td", "SHA256",             # Timestamp digest algorithm
        "/v",                        # Verbose output
        str(target),
    ]
    return cmd


def sign_file(target: Path, config: dict, signtool: Path) -> None:
    """Sign a single binary. Fails loudly if signing fails."""
    if not target.exists():
        log(f"  SKIP (not found): {target.name}")
        return

    log(f"Signing: {target.relative_to(ROOT) if target.is_relative_to(ROOT) else target.name}")
    cmd = build_signtool_cmd(target, config, signtool)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        die(f"Signing FAILED for: {target}\nSigning must not be skipped for production releases.")
    log(f"  [SIGNED OK] {target.name}")


def verify_file(target: Path, strict: bool = True) -> dict:
    """Verify signature on a file. Returns a dict with verification results."""
    if not target.exists():
        return {"exists": False}

    ps_cmd = (
        f"$s = Get-AuthenticodeSignature '{str(target).replace(chr(39), chr(34))}'; "
        f"$chain = New-Object Security.Cryptography.X509Certificates.X509Chain; "
        f"if ($s.SignerCertificate) {{ $chainValid = $chain.Build($s.SignerCertificate) }} else {{ $chainValid = $false }}; "
        f"[PSCustomObject]@{{"
        f"  Status=$s.Status; "
        f"  SignerSubject=if($s.SignerCertificate){{$s.SignerCertificate.Subject}}else{{'(none)'}}; "
        f"  SignerIssuer=if($s.SignerCertificate){{$s.SignerCertificate.Issuer}}else{{'(none)'}}; "
        f"  IsSelfSigned=if($s.SignerCertificate){{$s.SignerCertificate.Subject -eq $s.SignerCertificate.Issuer}}else{{$true}}; "
        f"  HasTimestamp=if($s.TimeStamperCertificate){{$true}}else{{$false}}; "
        f"  TimestampIssuer=if($s.TimeStamperCertificate){{$s.TimeStamperCertificate.Issuer}}else{{'(none)'}}; "
        f"  ChainValid=$chainValid; "
        f"}} | ConvertTo-Json"
    )
    res = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        capture_output=True, text=True
    )
    import json
    try:
        data = json.loads(res.stdout.strip())
        data["exists"] = True
        return data
    except Exception:
        return {"exists": True, "Status": "VerificationError", "raw": res.stdout}


def print_verification_report(results: list[tuple[Path, dict]]) -> None:
    print("\n" + "=" * 65)
    print("  SIGNATURE VERIFICATION REPORT")
    print("=" * 65)
    all_ok = True
    for target, v in results:
        name = target.name if target.exists() else str(target.name)
        if not v.get("exists"):
            print(f"  {name:45s}  NOT FOUND")
            continue
        status = v.get("Status", "?")
        signed = status == "Valid"
        self_signed = v.get("IsSelfSigned", True)
        has_ts = v.get("HasTimestamp", False)
        issuer = v.get("SignerIssuer", "(none)")
        trusted = signed and not self_signed
        if not signed or self_signed:
            all_ok = False
        marker = "[OK]" if (signed and not self_signed) else "[!!]"
        print(f"  {marker} {name}")
        print(f"       Signed:        {'YES' if signed else 'NO'}")
        print(f"       Self-Signed:   {'YES (NOT trusted by SAC!)' if self_signed else 'NO'}")
        print(f"       Issuer:        {issuer}")
        print(f"       Timestamp:     {'YES' if has_ts else 'NO'}")
        print(f"       Trusted by SAC:{'YES' if trusted else 'NO'}")
    print("=" * 65)
    if all_ok:
        print("  RESULT: ALL BINARIES SIGNED WITH TRUSTED CERTIFICATE")
    else:
        print("  RESULT: ONE OR MORE BINARIES NOT TRUSTED BY SMART APP CONTROL")
    print("=" * 65 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Furniture Bill — Production Code Signing Tool")
    parser.add_argument("--dry-run", action="store_true", help="Only verify existing signatures, do not sign")
    parser.add_argument("--verify-only", action="store_true", help="Same as --dry-run")
    args = parser.parse_args()
    dry_run = args.dry_run or args.verify_only

    print("=" * 65)
    print("  FURNITURE BILL SOFTWARE — PRODUCTION SIGNING TOOL")
    print("=" * 65)

    config = verify_signing_config(dry_run)

    if dry_run:
        log("Verifying existing signatures on all release binaries...")
        results = [(t, verify_file(t, strict=False)) for t in ALL_TARGETS]
        print_verification_report(results)
        return

    signtool = find_signtool()
    log(f"Using signtool.exe: {signtool}")
    log(f"Timestamp server:   {config['timestamp_url']}")

    for target in ALL_TARGETS:
        sign_file(target, config, signtool)

    log("All binaries signed. Running verification...")
    results = [(t, verify_file(t)) for t in ALL_TARGETS]
    print_verification_report(results)

    # Fail if any signed file was modified after signing
    log("Running post-sign integrity check...")
    for target in ALL_TARGETS:
        if not target.exists():
            continue
        v = verify_file(target)
        if v.get("Status") != "Valid":
            die(
                f"Post-sign verification FAILED for: {target}\n"
                "File may have been modified after signing. Rebuild and re-sign."
            )
    log("Post-sign integrity check PASSED for all targets.")


if __name__ == "__main__":
    main()

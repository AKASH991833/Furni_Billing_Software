"""Utility to zip the dist/FurnitureBill build for distribution."""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist" / "FurnitureBill"
OUTPUT_ZIP = ROOT / "dist" / "FurnitureBill_v1.0.0_Windows"

if not DIST_DIR.exists():
    print(f"Directory {DIST_DIR} does not exist. Run build_exe.bat first.")
    sys.exit(1)

print(f"Creating zip archive from {DIST_DIR}...")
archive_path = shutil.make_archive(str(OUTPUT_ZIP), "zip", DIST_DIR)
print(f"Successfully created: {archive_path}")

# Windows standalone build script.
#
# Produces a self-contained build of the application with PySide6, SQLAlchemy
# and the QtWebEngine PDF renderer bundled. The end user does not need to
# install Python or any dependency.

# 1. Install build tools (once):
#    pip install pyinstaller

# 2. Build:
#    python build_windows.py

# Output:
#   dist\FurnitureBill\FurnitureBill.exe   (one-folder build -- recommended)
#   OR dist\FurnitureBill.exe              (one-file build)

import os
import shutil
import subprocess
import sys

SPEC = "FurnitureBill.spec"


def ensure_icon():
    """Generate the app .ico from Qt if it does not exist."""
    ico = os.path.join("app", "resources", "icons", "app.ico")
    if os.path.exists(ico):
        return
    os.makedirs(os.path.dirname(ico), exist_ok=True)
    # Minimal valid ICO referencing the generated PNG is complex; instead
    # rely on the runtime icon as fallback. Create an empty placeholder note.
    print("No .ico found; the window icon is generated at runtime.")


def build():
    ensure_icon()
    args = ["python", "-m", "PyInstaller", "--noconfirm", "--clean", SPEC]
    subprocess.check_call(args)
    print("\nBuild complete.")
    print("Folder build output : dist\\FurnitureBill\\FurnitureBill.exe")
    print("To make a single-file exe instead, run:\n"
          "  python -m PyInstaller --noconfirm --onefile --name FurnitureBill run.py")


if __name__ == "__main__":
    build()

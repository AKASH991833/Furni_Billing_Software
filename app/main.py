"""Application entry point."""
from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from app.database.seed import init_app_data
    from app.ui.main_window import MainWindow
    from app.utils.paths import data_dir

    # Ensure DB exists and is seeded before UI is built.
    init_app_data()

    app = QApplication(sys.argv)
    app.setApplicationName("Furniture Bill")
    app.setOrganizationName("FurnitureBill")

    # A simple runtime-generated app icon (no external image dependency).
    icon = _make_icon()
    app.setWindowIcon(icon)

    window = MainWindow()
    window.show()
    rc = app.exec()
    return rc


def _make_icon() -> QIcon:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#2563EB"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(0, 0, 64, 64, 14, 14)
    painter.setPen(QColor("white"))
    font = painter.font()
    font.setPixelSize(30)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pm.rect(), Qt.AlignCenter, "\uD83E\uDEF0 F")
    painter.end()
    icon = QIcon(pm)
    return icon


if __name__ == "__main__":
    raise SystemExit(main())

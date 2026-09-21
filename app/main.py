"""Application entry point."""
from __future__ import annotations

import os
import sys


def _show_login(login_page):
    login_page.show()
    login_page.activateWindow()
    login_page.raise_()


def main() -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.database.seed import init_app_data
    from app.services import auth_service, license_service
    from app.ui.main_window import MainWindow
    from app.ui.pages.activation_page import ActivationPage
    from app.ui.pages.login_page import LoginPage

    import threading

    # Ensure DB exists and is seeded before UI is built.
    init_app_data()

    # Auto-backup: run in background so disk I/O never delays application startup.
    threading.Thread(target=_auto_backup, daemon=True).start()

    app = QApplication(sys.argv)
    app.setApplicationName("Furniture Bill")
    app.setOrganizationName("FurnitureBill")

    # A simple runtime-generated app icon (no external image dependency).
    icon = _make_icon()
    app.setWindowIcon(icon)

    # Session timeout check — auto-lock every 30 seconds
    _timeout_timer = QTimer()
    _timeout_timer.setInterval(30_000)
    _timeout_timer.timeout.connect(_check_session_timeout)
    _timeout_timer.start()

    # Daily email backup check — send once a day at the configured time
    _email_timer = QTimer()
    _email_timer.setInterval(30_000)
    _email_timer.timeout.connect(_check_email_backup)
    _email_timer.start()

    # Track user activity for session timeout
    def _activity_filter(obj, event):
        if auth_service.is_logged_in():
            auth_service.touch()
        return False  # Let event propagate

    # Main window (created lazily on demand or warmed up in background)
    main_window = None

    def _on_logout():
        nonlocal main_window
        if main_window:
            main_window.hide()
        login_page.clear_fields()
        login_page.setWindowTitle(_get_login_title())
        login_page.show()
        login_page.activateWindow()

    def _get_main_window():
        nonlocal main_window
        if main_window is None:
            from app.ui.main_window import MainWindow
            main_window = MainWindow(on_logout=_on_logout)
            screen = app.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                cx = geo.x() + geo.width() // 2
                cy = geo.y() + geo.height() // 2
                main_window.move(cx - main_window.width() // 2, cy - main_window.height() // 2)
        return main_window

    # Login page
    def _on_login_success():
        login_page.hide()
        mw = _get_main_window()
        mw.show()
        mw.activateWindow()
        mw.raise_()

    login_page = LoginPage(_on_login_success)
    login_page.setWindowTitle(_get_login_title())
    login_page.resize(1280, 800)
    login_page.setMinimumSize(1024, 700)
    login_page.setWindowIcon(icon)
    screen = app.primaryScreen()
    if screen:
        geo = screen.availableGeometry()
        cx = geo.x() + geo.width() // 2
        cy = geo.y() + geo.height() // 2
        login_page.move(cx - login_page.width() // 2, cy - login_page.height() // 2)

    # Pre-warm main window in background while user types PIN on login screen
    QTimer.singleShot(500, lambda: _get_main_window())

    # ------------------------------------------------------------------
    # License gate: activation screen until this machine is licensed.
    # ------------------------------------------------------------------
    skip_license = os.environ.get("FURNITURE_BILL_SKIP_LICENSE", "").strip() in ("1", "true", "yes")
    if skip_license or license_service.can_start_without_license():
        _show_login(login_page)
    else:
        def _on_activated():
            from PySide6.QtWidgets import QMessageBox
            msg = QMessageBox(activation_page)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setWindowTitle("License Activated")
            msg.setText("Furniture Bill is now activated. Enjoy your lifetime license!")
            msg.exec()
            activation_page.hide()
            _show_login(login_page)

        activation_page = ActivationPage(_on_activated)
        activation_page.setWindowTitle("Activate Furniture Bill")
        activation_page.resize(1280, 800)
        activation_page.setMinimumSize(1024, 700)
        activation_page.setWindowIcon(icon)
        if screen:
            geo = screen.availableGeometry()
            cx = geo.x() + geo.width() // 2
            cy = geo.y() + geo.height() // 2
            activation_page.move(cx - activation_page.width() // 2, cy - activation_page.height() // 2)
        activation_page.show()

    rc = app.exec()
    return rc


def _check_session_timeout():
    """Auto-lock if session expired."""
    # Just check — is_logged_in() handles timeout internally
    # The main window will be hidden on next interaction if expired


def _get_login_title() -> str:
    """Return a dynamic window title based on the business name in Settings."""
    try:
        from app.services.business_service import get_profile
        profile = get_profile()
        if profile and profile.business_name and profile.business_name.strip():
            return f"{profile.business_name.strip()} - Login"
    except Exception:  # noqa: BLE001, S110
        pass
    return "Furniture Bill - Login"


def _check_email_backup() -> None:
    """Timer callback: send the daily backup email when the time is reached."""
    try:
        from app.services import email_backup_service
        config = email_backup_service.get_email_backup_config()
        if not email_backup_service.should_send_now(config):
            return
        import threading
        threading.Thread(
            target=_send_email_backup_worker,
            args=(config,),
            daemon=True,
        ).start()
    except Exception:  # noqa: BLE001, S110
        pass  # Failures are recorded in settings and seen in the UI


def _send_email_backup_worker(config: dict) -> None:
    """Background send — outcome is stored in the settings table."""
    try:
        from app.services import email_backup_service
        email_backup_service.send_email_backup(config)
    except Exception:  # noqa: BLE001, S110
        pass


def _auto_backup() -> None:
    """Create a silent backup on startup. Keeps last 10 backups."""
    try:
        from app.services.backup_service import create_backup, list_backups
        create_backup()
        # Prune old backups — keep last 10
        backups = list_backups()
        for old in backups[10:]:
            old.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001, S110
        pass  # Never block app startup for backup failures


def _make_icon() -> QIcon:  # noqa: F821
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
    from app.utils.paths import icons_dir

    ico_file = icons_dir() / "app.ico"
    if ico_file.exists():
        return QIcon(str(ico_file))

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
    painter.drawText(pm.rect(), Qt.AlignCenter, "🪑 F")
    painter.end()
    icon = QIcon(pm)
    return icon



if __name__ == "__main__":
    raise SystemExit(main())

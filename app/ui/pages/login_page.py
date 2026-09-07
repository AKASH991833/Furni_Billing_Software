"""Login page — PIN-based authentication with forgot PIN flow.

Premium static-image background with:
  - Full-screen background image (local asset)
  - Glassmorphism card with subtle entrance animation
  - Dynamic business name and logo from Settings
  - Gold/amber accent, professional dark translucent card
"""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QColor,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services import auth_service, business_service
from app.utils.paths import login_background_path

# ---------------------------------------------------------------------------
# Background image widget — static, cached
# ---------------------------------------------------------------------------

_cached_bg_pixmap: QPixmap | None = None


def _get_bg_pixmap() -> QPixmap:
    """Return the cached background pixmap, loading from disk only once."""
    global _cached_bg_pixmap
    if _cached_bg_pixmap is not None and not _cached_bg_pixmap.isNull():
        return _cached_bg_pixmap
    path = login_background_path()
    _cached_bg_pixmap = QPixmap(str(path))
    return _cached_bg_pixmap


class LoginBackground(QWidget):
    """Static background image covering the full window, maintaining aspect ratio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter
        painter = QPainter(self)
        pixmap = _get_bg_pixmap()
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            # Fallback dark background if image is missing
            painter.fillRect(self.rect(), QColor(15, 23, 42))
        painter.end()


# ---------------------------------------------------------------------------
# Main Login Page
# ---------------------------------------------------------------------------

class LoginPage(QWidget):
    """PIN-based login screen with static image background and forgot PIN flow."""

    def __init__(self, on_login_success, parent=None):
        super().__init__(parent)
        self._on_login_success = on_login_success
        self._forgot_mode = False
        self._setup_ui()
        self._animation_started = False

    # ---- UI Setup ----

    def _setup_ui(self):
        # Background image — painted directly, fills entire widget
        self._bg = LoginBackground(self)

        # Overlay on top — transparent, holds the centered card
        self._overlay = QWidget(self)
        self._overlay.setAttribute(Qt.WA_TranslucentBackground)
        overlay_layout = QVBoxLayout(self._overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)
        overlay_layout.setContentsMargins(0, 0, 0, 0)

        # --- Card ---
        self._card = QFrame()
        self._card.setFixedSize(420, 520)
        self._card.setObjectName("loginCard")
        self._card.setStyleSheet("""
            QFrame#loginCard {
                background: rgba(15, 20, 35, 0.82);
                border: 1px solid rgba(199, 162, 75, 0.25);
                border-radius: 24px;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 120))
        self._card.setGraphicsEffect(shadow)

        self._card_layout = QVBoxLayout(self._card)
        self._card_layout.setContentsMargins(36, 28, 36, 24)
        self._card_layout.setSpacing(0)

        # --- Logo area (dynamic from Settings) ---
        self._logo_container = QWidget()
        self._logo_container.setFixedHeight(72)
        logo_layout = QVBoxLayout(self._logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setAlignment(Qt.AlignCenter)

        self._logo_label = QLabel()
        self._logo_label.setFixedSize(56, 56)
        self._logo_label.setAlignment(Qt.AlignCenter)
        self._logo_label.setStyleSheet(
            "background: rgba(199, 162, 75, 0.12); border: 1.5px solid rgba(199, 162, 75, 0.3);"
            " border-radius: 14px; font-size: 24px; color: #C7A24B;"
        )
        self._logo_label.setText("\u2726")
        logo_layout.addWidget(self._logo_label, 0, Qt.AlignCenter)

        self._card_layout.addWidget(self._logo_container)

        # --- Business name (dynamic from Settings) ---
        self._name_label = QLabel("Welcome")
        self._name_label.setAlignment(Qt.AlignCenter)
        self._name_label.setStyleSheet(
            "font-size: 22px; font-weight: 800; color: rgba(255,255,255,0.95);"
            " background: transparent; letter-spacing: 0.5px;"
        )
        self._card_layout.addWidget(self._name_label)

        self._card_layout.addSpacing(2)

        # Welcome back text
        self._welcome_label = QLabel("Welcome Back")
        self._welcome_label.setAlignment(Qt.AlignCenter)
        self._welcome_label.setStyleSheet(
            "font-size: 12px; color: rgba(199, 162, 75, 0.85);"
            " background: transparent; font-weight: 500; letter-spacing: 0.3px;"
        )
        self._card_layout.addWidget(self._welcome_label)

        self._card_layout.addSpacing(6)

        # Thin decorative gold divider
        self._divider = QFrame()
        self._divider.setFixedHeight(1)
        self._divider.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 rgba(199,162,75,0.0), stop:0.5 rgba(199,162,75,0.35),"
            "stop:1 rgba(199,162,75,0.0));"
        )
        self._card_layout.addWidget(self._divider)
        self._card_layout.addSpacing(10)

        # ============================================================
        # PIN mode widgets
        # ============================================================
        self._pin_widgets: list[QWidget] = []

        # Subtitle
        self._sub_label = QLabel("Enter your PIN to continue")
        self._sub_label.setAlignment(Qt.AlignCenter)
        self._sub_label.setStyleSheet(
            "font-size: 12px; color: rgba(255,255,255,0.50);"
            " background: transparent;"
        )
        self._pin_widgets.append(self._sub_label)
        self._card_layout.addWidget(self._sub_label)

        self._card_layout.addSpacing(10)

        # PIN label
        pin_label = QLabel("PIN")
        pin_label.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: rgba(199,162,75,0.7);"
            " background: transparent; margin-bottom: 2px; letter-spacing: 1.5px;"
        )
        self._pin_widgets.append(pin_label)
        self._card_layout.addWidget(pin_label)

        # PIN input row
        pin_row_widget = QWidget()
        pin_row = QHBoxLayout(pin_row_widget)
        pin_row.setContentsMargins(0, 0, 0, 0)
        pin_row.setSpacing(0)
        self.f_pin = QLineEdit()
        self.f_pin.setPlaceholderText("Enter 4-6 digit PIN")
        self.f_pin.setEchoMode(QLineEdit.EchoMode.Password)
        self.f_pin.setMaxLength(6)
        self.f_pin.setMinimumHeight(46)
        self.f_pin.setStyleSheet("""
            QLineEdit {
                border: 1.5px solid rgba(199, 162, 75, 0.25);
                border-right: none;
                border-top-left-radius: 12px;
                border-bottom-left-radius: 12px;
                padding: 8px 16px;
                font-size: 20px;
                letter-spacing: 8px;
                color: rgba(255, 255, 255, 0.95);
                background: rgba(255, 255, 255, 0.06);
                selection-background-color: rgba(199, 162, 75, 0.3);
            }
            QLineEdit:focus {
                border: 2px solid rgba(199, 162, 75, 0.5);
                border-right: none;
                background: rgba(255, 255, 255, 0.08);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.25);
                font-size: 13px;
                letter-spacing: 1px;
            }
        """)
        self.f_pin.returnPressed.connect(self._do_login)
        self.f_pin.textChanged.connect(self._auto_submit_pin)
        pin_row.addWidget(self.f_pin, 1)

        self._btn_eye = QPushButton("\U0001F441")
        self._btn_eye.setFixedSize(48, 46)
        self._btn_eye.setCursor(Qt.PointingHandCursor)
        self._btn_eye.setStyleSheet("""
            QPushButton {
                border: 1.5px solid rgba(199, 162, 75, 0.25);
                border-left: none;
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
                background: rgba(255, 255, 255, 0.06);
                font-size: 16px;
                color: rgba(255, 255, 255, 0.5);
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.12);
                color: rgba(255, 255, 255, 0.9);
            }
        """)
        self._btn_eye.clicked.connect(self._toggle_eye)
        pin_row.addWidget(self._btn_eye)

        self._pin_widgets.append(pin_row_widget)
        self._card_layout.addWidget(pin_row_widget)

        self._card_layout.addSpacing(4)

        # Error label
        self._error_label = QLabel("")
        self._error_label.setAlignment(Qt.AlignCenter)
        self._error_label.setStyleSheet(
            "font-size: 12px; color: #F87171; background: transparent;"
            " padding: 4px 0;"
        )
        self._error_label.setMinimumHeight(20)
        self._pin_widgets.append(self._error_label)
        self._card_layout.addWidget(self._error_label)

        self._card_layout.addSpacing(6)

        # Login button
        self._btn_login = QPushButton("LOGIN")
        self._btn_login.setMinimumHeight(46)
        self._btn_login.setCursor(Qt.PointingHandCursor)
        self._btn_login.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #A8852F, stop:0.4 #C7A24B, stop:0.7 #D4AF5A, stop:1 #C7A24B);
                color: #0F1729;
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: 800;
                letter-spacing: 2px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #C7A24B, stop:0.4 #D4AF5A, stop:0.7 #E6D9B8, stop:1 #D4AF5A);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8B6E22, stop:0.4 #A8852F, stop:0.7 #C7A24B, stop:1 #A8852F);
            }
        """)
        self._btn_login.clicked.connect(self._do_login)
        self._pin_widgets.append(self._btn_login)
        self._card_layout.addWidget(self._btn_login)

        self._card_layout.addSpacing(10)

        # Forgot PIN link
        self._btn_forgot = QPushButton("Forgot PIN?")
        self._btn_forgot.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: rgba(199, 162, 75, 0.65);
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover { color: rgba(199, 162, 75, 1.0); }
        """)
        self._btn_forgot.setCursor(Qt.PointingHandCursor)
        self._btn_forgot.clicked.connect(self._show_forgot)
        self._pin_widgets.append(self._btn_forgot)
        self._card_layout.addWidget(self._btn_forgot, 0, Qt.AlignCenter)

        self._card_layout.addStretch(1)

        # Offline indicator
        self._offline_label = QLabel("Offline \u2022 Your data stays on this device")
        self._offline_label.setAlignment(Qt.AlignCenter)
        self._offline_label.setStyleSheet(
            "font-size: 10px; color: rgba(255,255,255,0.25);"
            " background: transparent;"
        )
        self._pin_widgets.append(self._offline_label)
        self._card_layout.addWidget(self._offline_label)

        # ============================================================
        # Forgot PIN mode widgets
        # ============================================================
        self._forgot_widgets: list[QWidget] = []

        self._forgot_sub = QLabel("Reset PIN")
        self._forgot_sub.setAlignment(Qt.AlignCenter)
        self._forgot_sub.setStyleSheet(
            "font-size: 16px; font-weight: 700; color: rgba(255,255,255,0.95);"
            " background: transparent; letter-spacing: 0.3px;"
        )
        self._forgot_widgets.append(self._forgot_sub)
        self._card_layout.addWidget(self._forgot_sub)

        self._forgot_hint = QLabel(
            "Verify your account to reset your PIN."
        )
        self._forgot_hint.setAlignment(Qt.AlignCenter)
        self._forgot_hint.setWordWrap(True)
        self._forgot_hint.setStyleSheet(
            "font-size: 11px; color: rgba(255,255,255,0.5);"
            " background: transparent; line-height: 1.4;"
        )
        self._forgot_widgets.append(self._forgot_hint)
        self._card_layout.addWidget(self._forgot_hint)

        self._card_layout.addSpacing(10)

        # Verification label
        recover_label = QLabel("VERIFICATION INFORMATION")
        recover_label.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: rgba(199,162,75,0.6);"
            " background: transparent; margin-bottom: 2px; letter-spacing: 1.2px;"
        )
        self._forgot_widgets.append(recover_label)
        self._card_layout.addWidget(recover_label)

        # Verification input
        recover_row_widget = QWidget()
        recover_row = QHBoxLayout(recover_row_widget)
        recover_row.setContentsMargins(0, 0, 0, 0)
        recover_row.setSpacing(0)
        self.f_recover = QLineEdit()
        self.f_recover.setPlaceholderText("Enter verification details")
        self.f_recover.setMinimumHeight(46)
        self.f_recover.setStyleSheet("""
            QLineEdit {
                border: 1.5px solid rgba(199, 162, 75, 0.25);
                border-right: none;
                border-top-left-radius: 12px;
                border-bottom-left-radius: 12px;
                padding: 8px 16px;
                font-size: 14px;
                color: rgba(255, 255, 255, 0.95);
                background: rgba(255, 255, 255, 0.06);
                selection-background-color: rgba(199, 162, 75, 0.3);
            }
            QLineEdit:focus {
                border: 2px solid rgba(199, 162, 75, 0.5);
                border-right: none;
                background: rgba(255, 255, 255, 0.08);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.25);
            }
        """)
        self.f_recover.returnPressed.connect(self._do_recover)
        recover_row.addWidget(self.f_recover, 1)

        self._btn_recover_eye = QPushButton("\U0001F441")
        self._btn_recover_eye.setFixedSize(48, 46)
        self._btn_recover_eye.setCursor(Qt.PointingHandCursor)
        self._btn_recover_eye.setStyleSheet("""
            QPushButton {
                border: 1.5px solid rgba(199, 162, 75, 0.25);
                border-left: none;
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
                background: rgba(255, 255, 255, 0.06);
                font-size: 16px;
                color: rgba(255, 255, 255, 0.5);
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.12);
                color: rgba(255, 255, 255, 0.9);
            }
        """)
        self._btn_recover_eye.clicked.connect(self._toggle_recover_eye)
        recover_row.addWidget(self._btn_recover_eye)

        self._forgot_widgets.append(recover_row_widget)
        self._card_layout.addWidget(recover_row_widget)

        self._card_layout.addSpacing(4)

        # Forgot error label
        self._forgot_error = QLabel("")
        self._forgot_error.setAlignment(Qt.AlignCenter)
        self._forgot_error.setStyleSheet(
            "font-size: 12px; color: #F87171; background: transparent;"
            " padding: 4px 0;"
        )
        self._forgot_error.setMinimumHeight(20)
        self._forgot_widgets.append(self._forgot_error)
        self._card_layout.addWidget(self._forgot_error)

        self._card_layout.addSpacing(6)

        # Verify button
        self._btn_verify = QPushButton("Verify")
        self._btn_verify.setMinimumHeight(46)
        self._btn_verify.setCursor(Qt.PointingHandCursor)
        self._btn_verify.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #A8852F, stop:0.4 #C7A24B, stop:0.7 #D4AF5A, stop:1 #C7A24B);
                color: #0F1729;
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: 800;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #C7A24B, stop:0.4 #D4AF5A, stop:0.7 #E6D9B8, stop:1 #D4AF5A);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8B6E22, stop:0.4 #A8852F, stop:0.7 #C7A24B, stop:1 #A8852F);
            }
        """)
        self._btn_verify.clicked.connect(self._do_recover)
        self._forgot_widgets.append(self._btn_verify)
        self._card_layout.addWidget(self._btn_verify)

        self._card_layout.addSpacing(8)

        # Back to login
        self._btn_back = QPushButton("\u2190  Back to Login")
        self._btn_back.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: rgba(199, 162, 75, 0.6);
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover { color: rgba(199, 162, 75, 1.0); }
        """)
        self._btn_back.setCursor(Qt.PointingHandCursor)
        self._btn_back.clicked.connect(self._show_login)
        self._forgot_widgets.append(self._btn_back)
        self._card_layout.addWidget(self._btn_back, 0, Qt.AlignCenter)

        self._card_layout.addStretch(1)

        # Initially hide forgot widgets
        for w in self._forgot_widgets:
            w.hide()

        overlay_layout.addWidget(self._card, 0, Qt.AlignCenter)

        # Load dynamic data
        self._refresh_dynamic_data()

    def resizeEvent(self, event):
        """Keep background and overlay covering the full window."""
        super().resizeEvent(event)
        size = self.size()
        self._bg.setGeometry(0, 0, size.width(), size.height())
        self._overlay.setGeometry(0, 0, size.width(), size.height())
        # Re-center the card after the overlay resizes
        card_size = self._card.size()
        x = (size.width() - card_size.width()) // 2
        y = (size.height() - card_size.height()) // 2
        self._card.move(x, y)

    # ---- Dynamic data from Settings ----

    def _refresh_dynamic_data(self):
        """Load business name and logo from the database."""
        profile = business_service.get_profile()

        # Business name
        biz_name = ""
        if profile and profile.business_name:
            biz_name = profile.business_name.strip()
        if biz_name:
            self._name_label.setText(biz_name)
        else:
            self._name_label.setText("Welcome")

        # Logo
        if profile and profile.logo_path:
            from pathlib import Path
            if Path(profile.logo_path).exists():
                pm = QPixmap(profile.logo_path)
                if not pm.isNull():
                    scaled = pm.scaled(
                        48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    self._logo_label.setPixmap(scaled)
                    self._logo_label.setText("")
                    self._logo_label.setStyleSheet(
                        "background: rgba(199, 162, 75, 0.12);"
                        " border: 1.5px solid rgba(199, 162, 75, 0.3);"
                        " border-radius: 14px;"
                    )
                    return
        # Default icon when no logo
        self._logo_label.setPixmap(QPixmap())
        self._logo_label.setText("\u2726")
        self._logo_label.setStyleSheet(
            "background: rgba(199, 162, 75, 0.12);"
            " border: 1.5px solid rgba(199, 162, 75, 0.3);"
            " border-radius: 14px; font-size: 24px; color: #C7A24B;"
        )

    # ---- Entrance Animation ----

    def _run_entrance_animation(self):
        """Subtle fade-in + slide-up entrance for the card."""
        # Ensure the card is centered before calculating animation positions
        size = self.size()
        card_size = self._card.size()
        centered_x = (size.width() - card_size.width()) // 2
        centered_y = (size.height() - card_size.height()) // 2
        self._card.move(centered_x, centered_y)

        start_pos = QPoint(centered_x, centered_y + 30)
        end_pos = QPoint(centered_x, centered_y)

        self._card.move(start_pos)

        self._card_opacity = QGraphicsOpacityEffect(self._card)
        self._card_opacity.setOpacity(0.0)
        self._card.setGraphicsEffect(self._card_opacity)

        # Opacity: 0 -> 1
        self._fade_anim = QPropertyAnimation(self._card_opacity, b"opacity")
        self._fade_anim.setDuration(500)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)

        # Slide up
        self._slide_anim = QPropertyAnimation(self._card, b"pos")
        self._slide_anim.setDuration(500)
        self._slide_anim.setStartValue(start_pos)
        self._slide_anim.setEndValue(end_pos)
        self._slide_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._fade_anim.start()
        self._slide_anim.start()

    # ---- Mode switching ----

    def _show_forgot(self):
        """Switch to forgot PIN mode."""
        self._forgot_mode = True
        self._refresh_dynamic_data()
        for w in self._pin_widgets:
            w.hide()
        self._show_forgot_error("")
        self.f_recover.clear()
        self._btn_verify.setText("Verify")
        try:
            self._btn_verify.clicked.disconnect()
        except RuntimeError:
            pass
        self._btn_verify.clicked.connect(self._do_recover)
        self._btn_back.show()
        self._forgot_hint.setStyleSheet(
            "font-size: 11px; color: rgba(255,255,255,0.5);"
            " background: transparent; line-height: 1.4;"
        )
        self._forgot_hint.setText("Verify your account to reset your PIN.")
        self._forgot_sub.setText("Reset PIN")
        self._forgot_sub.setStyleSheet(
            "font-size: 16px; font-weight: 700; color: rgba(255,255,255,0.95);"
            " background: transparent; letter-spacing: 0.3px;"
        )
        self.f_recover.setEchoMode(QLineEdit.EchoMode.Normal)
        self.f_recover.setPlaceholderText("Enter verification details")
        for w in self._forgot_widgets:
            w.show()
        QTimer.singleShot(100, lambda: self.f_recover.setFocus())

    def _show_login(self):
        """Switch back to login mode."""
        self._forgot_mode = False
        for w in self._forgot_widgets:
            w.hide()
        self._error_label.setText("")
        self.f_pin.clear()
        self._refresh_dynamic_data()
        for w in self._pin_widgets:
            w.show()
        QTimer.singleShot(100, lambda: self.f_pin.setFocus())

    # ---- Eye toggle ----

    def _toggle_eye(self):
        if self.f_pin.echoMode() == QLineEdit.EchoMode.Password:
            self.f_pin.setEchoMode(QLineEdit.EchoMode.Normal)
            self._btn_eye.setText("\U0001F648")
        else:
            self.f_pin.setEchoMode(QLineEdit.EchoMode.Password)
            self._btn_eye.setText("\U0001F441")

    def _toggle_recover_eye(self):
        if self.f_recover.echoMode() == QLineEdit.EchoMode.Password:
            self.f_recover.setEchoMode(QLineEdit.EchoMode.Normal)
            self._btn_recover_eye.setText("\U0001F648")
        else:
            self.f_recover.setEchoMode(QLineEdit.EchoMode.Password)
            self._btn_recover_eye.setText("\U0001F441")

    # ---- Login ----

    def _auto_submit_pin(self, text: str):
        """Auto-login when PIN reaches 4-6 digits."""
        pin = text.strip()
        if len(pin) >= 4:
            self._do_login()

    def _do_login(self):
        pin = self.f_pin.text().strip()
        if not pin:
            self._show_error("Please enter your PIN.")
            return

        success, message = auth_service.login(pin)
        if success:
            self._error_label.setText("")
            self._on_login_success()
        else:
            self._show_error(message)
            self.f_pin.clear()
            self.f_pin.setFocus()

    # ---- Forgot PIN recovery ----

    def _do_recover(self):
        text = self.f_recover.text().strip()
        if not text:
            self._show_forgot_error("Please enter your verification information.")
            return

        # Parse: extract digits (mobile) and letters (name) from combined input
        digits = "".join(c for c in text if c.isdigit())
        letters = "".join(c for c in text if c.isalpha())

        if len(digits) < 10 or not letters:
            self._show_forgot_error(
                "Verification failed. Please check your information and try again."
            )
            return

        mobile = digits[-10:]
        name = letters.lower()

        ok, message = auth_service.recover_pin(mobile, name)
        if ok:
            self._show_forgot_error("")
            self._forgot_sub.setText("Create New PIN")
            self._forgot_hint.setText("Identity verified. Create your new PIN.")
            self._forgot_hint.setStyleSheet(
                "font-size: 11px; color: #34D399; background: transparent;"
                " font-weight: 600;"
            )
            self.f_recover.setPlaceholderText("Enter new 4-6 digit PIN")
            self.f_recover.clear()
            self.f_recover.setEchoMode(QLineEdit.EchoMode.Password)
            self._btn_verify.setText("Set New PIN")
            self._btn_verify.clicked.disconnect()
            self._btn_verify.clicked.connect(self._do_set_new_pin)
            self._btn_back.hide()
        else:
            self._show_forgot_error(message)

    def _do_set_new_pin(self):
        pin = self.f_recover.text().strip()
        if not pin:
            self._show_forgot_error("Please enter a new PIN.")
            return

        ok, message = auth_service.set_new_pin(pin)
        if ok:
            self._show_login()
            self._error_label.setText("PIN reset successful! Please login.")
            self._error_label.setStyleSheet(
                "font-size: 12px; color: #34D399; background: transparent;"
            )
            QTimer.singleShot(3000, lambda: self._error_label.setStyleSheet(
                "font-size: 12px; color: #F87171; background: transparent;"
            ))
        else:
            self._show_forgot_error(message)

    # ---- Error Helpers ----

    def _show_error(self, msg: str):
        self._error_label.setText(msg)
        # Red border flash
        self.f_pin.setStyleSheet("""
            QLineEdit {
                border: 2px solid rgba(248, 113, 113, 0.7);
                border-right: none;
                border-top-left-radius: 12px;
                border-bottom-left-radius: 12px;
                padding: 8px 16px;
                font-size: 20px;
                letter-spacing: 8px;
                color: rgba(255, 255, 255, 0.95);
                background: rgba(248, 113, 113, 0.08);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.25);
                font-size: 13px;
                letter-spacing: 1px;
            }
        """)
        QTimer.singleShot(1500, self._reset_pin_style)

    def _reset_pin_style(self):
        self.f_pin.setStyleSheet("""
            QLineEdit {
                border: 1.5px solid rgba(199, 162, 75, 0.25);
                border-right: none;
                border-top-left-radius: 12px;
                border-bottom-left-radius: 12px;
                padding: 8px 16px;
                font-size: 20px;
                letter-spacing: 8px;
                color: rgba(255, 255, 255, 0.95);
                background: rgba(255, 255, 255, 0.06);
                selection-background-color: rgba(199, 162, 75, 0.3);
            }
            QLineEdit:focus {
                border: 2px solid rgba(199, 162, 75, 0.5);
                border-right: none;
                background: rgba(255, 255, 255, 0.08);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.25);
                font-size: 13px;
                letter-spacing: 1px;
            }
        """)

    def _show_forgot_error(self, msg: str):
        self._forgot_error.setText(msg)

    def clear_fields(self):
        """Clear all fields."""
        self.f_pin.clear()
        self.f_recover.clear()
        self._error_label.setText("")
        self._forgot_error.setText("")
        if self._forgot_mode:
            self._show_login()

    def showEvent(self, event):
        """Refresh dynamic data and start entrance animation after geometry is available."""
        super().showEvent(event)
        self._refresh_dynamic_data()
        if not self._animation_started:
            self._animation_started = True
            # Defer animation so the layout has time to center the card first
            QTimer.singleShot(0, self._run_entrance_animation)

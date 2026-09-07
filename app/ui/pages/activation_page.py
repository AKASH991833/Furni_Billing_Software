"""Activation page — license key entry shown when no valid license exists.

Mirrors the login screen's glassmorphism look so activation feels like part of
the product, not an afterthought.
"""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QPixmap
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

from app.services import license_service
from app.utils.paths import login_background_path

_CARD_STYLE = """
QFrame#activationCard {
    background: rgba(15, 20, 35, 0.86);
    border: 1px solid rgba(199, 162, 75, 0.25);
    border-radius: 24px;
}
"""

_INPUT_STYLE = """
QLineEdit {
    border: 1.5px solid rgba(199, 162, 75, 0.25);
    border-radius: 12px;
    padding: 10px 16px;
    font-size: 15px;
    letter-spacing: 0.6px;
    color: rgba(255, 255, 255, 0.95);
    background: rgba(255, 255, 255, 0.06);
    selection-background-color: rgba(199, 162, 75, 0.3);
}
QLineEdit:focus {
    border: 2px solid rgba(199, 162, 75, 0.5);
    background: rgba(255, 255, 255, 0.08);
}
QLineEdit::placeholder {
    color: rgba(255, 255, 255, 0.28);
    font-size: 13px;
}
"""

_BUTTON_STYLE = """
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
QPushButton:disabled {
    background: rgba(199, 162, 75, 0.25);
    color: rgba(15, 23, 41, 0.4);
}
"""

_EXIT_BUTTON_STYLE = """
QPushButton {
    background: rgba(255, 255, 255, 0.06);
    color: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(199, 162, 75, 0.25);
    border-radius: 12px;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 1.5px;
}
QPushButton:hover {
    background: rgba(255, 255, 255, 0.12);
    color: rgba(255, 255, 255, 0.95);
    border-color: rgba(199, 162, 75, 0.5);
}
QPushButton:pressed {
    background: rgba(255, 255, 255, 0.04);
}
QPushButton:disabled {
    background: rgba(255, 255, 255, 0.02);
    color: rgba(255, 255, 255, 0.2);
}
"""


class ActivationBackground(QWidget):
    """Static background image covering the full window."""

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter

        painter = QPainter(self)
        pm = QPixmap(str(login_background_path()))
        if not pm.isNull():
            scaled = pm.scaled(
                self.size(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            painter.fillRect(self.rect(), QColor(15, 23, 42))
        painter.end()


class ActivationPage(QWidget):
    """License activation screen. Calls `on_activated()` after success."""

    def __init__(self, on_activated, parent=None):
        super().__init__(parent)
        self._on_activated = on_activated
        self._busy = False
        self._setup_ui()
        self._animation_started = False

    # ---- UI ----

    def _setup_ui(self):
        self._font = None
        self.resized_flag = False
        self._bg = ActivationBackground(self)

        self._overlay = QWidget(self)
        self._overlay.setAttribute(Qt.WA_TranslucentBackground)
        overlay_layout = QVBoxLayout(self._overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)
        overlay_layout.setContentsMargins(0, 0, 0, 0)

        self._card = QFrame()
        self._card.setFixedSize(450, 580)
        self._card.setObjectName("activationCard")
        self._card.setStyleSheet(_CARD_STYLE)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 120))
        self._card.setGraphicsEffect(shadow)

        self._card_layout = QVBoxLayout(self._card)
        self._card_layout.setContentsMargins(36, 28, 36, 24)
        self._card_layout.setSpacing(8)

        # Logo mark
        logo = QLabel("\u2726")
        logo.setFixedSize(56, 56)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(
            "background: rgba(199, 162, 75, 0.12); border: 1.5px solid rgba(199, 162, 75, 0.3);"
            " border-radius: 14px; font-size: 26px; color: #C7A24B;"
        )
        self._card_layout.addWidget(logo, 0, Qt.AlignCenter)

        self._card_layout.addSpacing(4)

        self._title = QLabel("Software Activation")
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setStyleSheet(
            "font-size: 21px; font-weight: 800; color: rgba(255,255,255,0.95);"
            " background: transparent; letter-spacing: 0.5px;"
        )
        self._card_layout.addWidget(self._title)

        self._subtitle = QLabel(
            "Internet connection is required for first activation."
        )
        self._subtitle.setAlignment(Qt.AlignCenter)
        self._subtitle.setWordWrap(True)
        self._subtitle.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #C7A24B;"
            " background: transparent; line-height: 1.4;"
        )
        self._card_layout.addWidget(self._subtitle)

        self._card_layout.addSpacing(6)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 rgba(199,162,75,0.0), stop:0.5 rgba(199,162,75,0.35),"
            "stop:1 rgba(199,162,75,0.0));"
        )
        self._card_layout.addWidget(divider)

        self._card_layout.addSpacing(8)

        key_label = QLabel("LICENSE KEY")
        key_label.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: rgba(199,162,75,0.7);"
            " background: transparent; letter-spacing: 1.2px;"
        )
        self._card_layout.addWidget(key_label)

        key_row = QWidget()
        key_layout = QHBoxLayout(key_row)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(0)
        self.f_key = QLineEdit()
        self.f_key.setPlaceholderText("FB-XXXX-XXXX-XXXX")
        self.f_key.setMaxLength(40)
        self.f_key.setMinimumHeight(46)
        self.f_key.setStyleSheet(_INPUT_STYLE)
        self.f_key.returnPressed.connect(self._do_activate)
        self.f_key.textChanged.connect(self._on_text_changed)
        key_layout.addWidget(self.f_key, 1)
        self._card_layout.addWidget(key_row)

        self._card_layout.addSpacing(4)

        self._error_label = QLabel("")
        self._error_label.setAlignment(Qt.AlignCenter)
        self._error_label.setWordWrap(True)
        self._error_label.setMinimumHeight(40)
        self._error_label.setStyleSheet(
            "font-size: 12px; color: #F87171; background: transparent; padding: 4px 0;"
        )
        self._card_layout.addWidget(self._error_label)

        # Buttons: Activate and Exit
        btn_box = QWidget()
        btn_layout = QHBoxLayout(btn_box)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(10)

        self._btn_activate = QPushButton("ACTIVATE")
        self._btn_activate.setMinimumHeight(46)
        self._btn_activate.setCursor(Qt.PointingHandCursor)
        self._btn_activate.setStyleSheet(_BUTTON_STYLE)
        self._btn_activate.clicked.connect(self._do_activate)
        btn_layout.addWidget(self._btn_activate, 2)

        self._btn_exit = QPushButton("EXIT")
        self._btn_exit.setMinimumHeight(46)
        self._btn_exit.setCursor(Qt.PointingHandCursor)
        self._btn_exit.setStyleSheet(_EXIT_BUTTON_STYLE)
        self._btn_exit.clicked.connect(self._do_exit)
        btn_layout.addWidget(self._btn_exit, 1)

        self._card_layout.addWidget(btn_box)

        self._card_layout.addSpacing(10)

        self._help = QLabel(
            "One-time activation · Lifetime license · Works offline after setup",
        )
        self._help.setAlignment(Qt.AlignCenter)
        self._help.setWordWrap(True)
        self._help.setStyleSheet(
            "font-size: 10.5px; color: rgba(255,255,255,0.35);"
            " background: transparent; line-height: 1.4;"
        )
        self._card_layout.addWidget(self._help)

        self._card_layout.addStretch(1)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(
            "font-size: 10px; color: rgba(255,255,255,0.25); background: transparent;"
        )
        self._card_layout.addWidget(self._status_label)

    # ---- Behavior ----

    def _on_text_changed(self):
        if self._error_label.text():
            self._error_label.setText("")

    def _do_exit(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.quit()
        else:
            self.close()

    def _do_activate(self):
        if self._busy:
            return
        key = self.f_key.text().strip()
        if not key:
            self._show_error("Please enter your license key.")
            return

        self._busy = True
        self._btn_activate.setEnabled(False)
        self._status_label.setText("Activating\u2026 please wait.")
        self._status_label.setStyleSheet(
            "font-size: 10px; color: rgba(199,162,75,0.8); background: transparent;"
        )
        QTimer.singleShot(0, lambda: self._activate_async(key))

    def _activate_async(self, key: str):
        try:
            license_service.activate_online(key)
        except Exception as exc:  # noqa: BLE001 - user-facing message
            self._show_error(str(exc) or "Activation failed. Please try again.")
            self._busy = False
            self._btn_activate.setEnabled(True)
            self._status_label.setText("")
            return
        self._busy = False
        self._status_label.setText("")
        if self._on_activated:
            self._on_activated()

    def _show_error(self, message: str):
        self._error_label.setText(message)

    def resizeEvent(self, event):
        """Keep background and overlay covering the full window."""
        super().resizeEvent(event)
        size = self.size()
        self._bg.setGeometry(0, 0, size.width(), size.height())
        self._overlay.setGeometry(0, 0, size.width(), size.height())
        card_size = self._card.size()
        x = (size.width() - card_size.width()) // 2
        y = (size.height() - card_size.height()) // 2
        self._card.move(x, y)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._animation_started:
            self._animation_started = True
            QTimer.singleShot(0, self._run_entrance_animation)
        self.f_key.setFocus()

    def _run_entrance_animation(self):
        card = self._card
        if card.width() <= 0 or self.width() <= 0:
            centered_x = (self.width() - card.width()) // 2
            centered_y = (self.height() - card.height()) // 2
        else:
            centered_x = (self.width() - card.width()) // 2
            centered_y = (self.height() - card.height()) // 2

        opacity = QGraphicsOpacityEffect(card)
        card.setGraphicsEffect(opacity)
        fade = QPropertyAnimation(opacity, b"opacity", self)
        fade.setDuration(450)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.start(QPropertyAnimation.DeleteWhenStopped)

        slide = QPropertyAnimation(card, b"pos", self)
        slide.setDuration(450)
        slide.setStartValue(QPoint(centered_x, centered_y + 30))
        slide.setEndValue(QPoint(centered_x, centered_y))
        slide.setEasingCurve(QEasingCurve.OutCubic)
        slide.start(QPropertyAnimation.DeleteWhenStopped)
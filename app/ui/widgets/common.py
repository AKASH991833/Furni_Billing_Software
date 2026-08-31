"""Reusable UI widgets: cards, toast, empty states, helpers."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.style import PRIMARY


def stat_card(title: str, value: str, accent: str = PRIMARY) -> QFrame:
    card = QFrame()
    card.setObjectName("card")
    card.setStyleSheet(f"QFrame#card {{ border-left: 4px solid {accent}; }}")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(4)
    v = QLabel(value)
    v.setObjectName("statValue")
    v.setStyleSheet(f"color: {accent};")
    t = QLabel(title)
    t.setObjectName("statLabel")
    lay.addWidget(v)
    lay.addWidget(t)
    return card


def empty_state(title: str, subtitle: str) -> QFrame:
    w = QFrame()
    w.setObjectName("card")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(24, 40, 24, 40)
    lay.setAlignment(Qt.AlignCenter)
    lay.setSpacing(8)
    icon = QLabel("\uD83D\uDCCB")
    icon.setAlignment(Qt.AlignCenter)
    icon.setStyleSheet("font-size: 40px;")
    t = QLabel(title)
    t.setObjectName("emptyTitle")
    t.setAlignment(Qt.AlignCenter)
    s = QLabel(subtitle)
    s.setObjectName("emptySub")
    s.setAlignment(Qt.AlignCenter)
    s.setWordWrap(True)
    lay.addWidget(icon)
    lay.addWidget(t)
    lay.addWidget(s)
    return w


class Toast(QFrame):
    """Floating toast/status notification."""

    def __init__(self, parent: QWidget, message: str, kind: str = "info"):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setStyleSheet(
            "QFrame#toast { background: #1F2937; border-radius: 10px; }"
            "QFrame#toastSuccess { background: #059669; }"
            "QFrame#toastError { background: #DC2626; }"
            "QLabel { color: white; font-weight: 500; padding: 4px; }"
        )
        if kind == "success":
            self.setObjectName("toastSuccess")
        elif kind == "error":
            self.setObjectName("toastError")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        label = QLabel(message)
        label.setObjectName("toastLabel")
        lay.addWidget(label)
        self.adjustSize()
        self._reposition()
        self.show()
        self._fade_in()

    def _reposition(self):
        parent = self.parentWidget()
        if parent:
            x = parent.width() - self.width() - 24
            y = parent.height() - self.height() - 24
            self.move(max(x, 0), max(y, 0))
        elif self.parent():
            self.move(self.parent().width() - self.width() - 20,
                      self.parent().height() - self.height() - 20)

    def _fade_in(self):
        self.setWindowOpacity(0)
        self.anim = QPropertyAnimation(self, b"windowOpacity", self)
        self.anim.setDuration(180)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()
        QTimer.singleShot(3200, self._fade_out)

    def _fade_out(self):
        self.anim = QPropertyAnimation(self, b"windowOpacity", self)
        self.anim.setDuration(300)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.finished.connect(self.deleteLater)
        self.anim.start()


def show_toast(parent: QWidget, message: str, kind: str = "info"):
    toast = Toast(parent, message, kind)
    toast.show()
    return toast


def primary_button(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName("primaryButton")
    b.setCursor(Qt.PointingHandCursor)
    return b


def card(title: str, widget: QWidget | None = None) -> QFrame:
    c = QFrame()
    c.setObjectName("card")
    v = QVBoxLayout(c)
    v.setContentsMargins(16, 16, 16, 16)
    v.setSpacing(12)
    t = QLabel(title)
    t.setObjectName("cardTitle")
    v.addWidget(t)
    if widget is not None:
        v.addWidget(widget)
    return c

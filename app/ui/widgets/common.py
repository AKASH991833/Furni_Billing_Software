"""Reusable UI widgets: animated glass cards, toast, empty states, helpers.

Provides frosted glass cards with subtle hover animations using
QPropertyGeometry for smooth scale effects.
"""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.style import (
    GLASS_FROSTED_LIGHT,
    GLASS_FROSTED_MEDIUM,
    GLASS_HOVER_GLOW,
    PRIMARY,
)


def _dark_or_light(dark_val: str, light_val: str) -> str:
    """Return light_val (dark mode removed — kept for call-site compatibility)."""
    return light_val


# ---------------------------------------------------------------------------
# Animated Glass Card
# ---------------------------------------------------------------------------

class GlassCard(QFrame):
    """A frosted glass card with subtle hover animation.

    Animates:
      - Border glow (color change via stylesheet)
      - Slight elevation (geometry shift up by 2px on hover)
      - Background brightness (gradient swap)
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        accent: str | None = None,
        hover_glow: bool = True,
        animate_geometry: bool = True,
    ):
        super().__init__(parent)
        self.setObjectName("glassCard")
        self._accent = accent
        self._hover_glow = hover_glow
        self._animate_geometry = animate_geometry
        self._is_hovered = False
        self._original_geometry = None
        self._setup_style()
        self.setMouseTracking(True)

    def _setup_style(self):
        accent_css = f"border-left: 4px solid {self._accent};" if self._accent else ""
        bg = _dark_or_light(
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(31,41,55,0.92), stop:1 rgba(26,34,47,0.82))",
            GLASS_FROSTED_LIGHT,
        )
        border = _dark_or_light("rgba(55, 65, 81, 0.5)", "rgba(200, 210, 230, 0.5)")
        self.setStyleSheet(f"""
            QFrame#glassCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 14px;
                {accent_css}
            }}
        """)

    def enterEvent(self, event):
        self._is_hovered = True
        if self._hover_glow:
            accent_css = f"border-left: 4px solid {self._accent};" if self._accent else ""
            bg = _dark_or_light(
                "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(55,65,81,0.95), stop:1 rgba(50,60,76,0.88))",
                GLASS_HOVER_GLOW,
            )
            border = _dark_or_light("rgba(59, 130, 246, 0.35)", "rgba(37, 99, 235, 0.25)")
            self.setStyleSheet(f"""
                QFrame#glassCard {{
                    background: {bg};
                    border: 1px solid {border};
                    border-radius: 14px;
                    {accent_css}
                }}
            """)
        if self._animate_geometry and self._original_geometry is None:
            self._original_geometry = self.geometry()
            g = self.geometry()
            self._anim = QPropertyAnimation(self, b"geometry")
            self._anim.setDuration(150)
            self._anim.setStartValue(g)
            self._anim.setEndValue(g.adjusted(0, -2, 0, 0))
            self._anim.setEasingCurve(QEasingCurve.OutCubic)
            self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        self._setup_style()
        if self._animate_geometry and self._original_geometry is not None:
            g = self.geometry()
            self._anim = QPropertyAnimation(self, b"geometry")
            self._anim.setDuration(200)
            self._anim.setStartValue(g)
            self._anim.setEndValue(self._original_geometry)
            self._anim.setEasingCurve(QEasingCurve.OutCubic)
            self._anim.start()
            self._original_geometry = None
        super().leaveEvent(event)


# ---------------------------------------------------------------------------
# Animated Stat Card (with count-up)
# ---------------------------------------------------------------------------

class AnimatedStatCard(QFrame):
    """Dashboard stat card with frosted glass and optional count-up animation."""

    def __init__(
        self,
        title: str,
        value: str,
        accent: str = PRIMARY,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("glassCard")
        self._accent = accent
        self._is_hovered = False
        self._original_geometry = None
        self._setup_style()
        self.setMouseTracking(True)
        self._build_ui(title, value)

    def _setup_style(self):
        bg = _dark_or_light(
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(31,41,55,0.92), stop:1 rgba(26,34,47,0.82))",
            GLASS_FROSTED_LIGHT,
        )
        border = _dark_or_light("rgba(55, 65, 81, 0.5)", "rgba(200, 210, 230, 0.5)")
        self.setStyleSheet(f"""
            QFrame#glassCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 14px;
                border-left: 4px solid {self._accent};
            }}
        """)

    def _build_ui(self, title: str, value: str):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(4)

        self._value_label = QLabel(value)
        self._value_label.setObjectName("statValue")
        self._value_label.setStyleSheet(f"color: {self._accent};")
        lay.addWidget(self._value_label)

        self._title_label = QLabel(title)
        self._title_label.setObjectName("statLabel")
        lay.addWidget(self._title_label)

    def set_value(self, value: str):
        self._value_label.setText(value)

    def animate_count_to(self, target: int, duration: int = 600):
        """Animate the stat value from 0 to target with easing."""
        self._target = target
        self._current_val = 0
        self._timer = QTimer(self)
        steps = 30
        self._step_ms = duration // steps
        self._step_val = max(target / steps, 1)
        self._timer.timeout.connect(self._count_step)
        self._timer.start(self._step_ms)

    def _count_step(self):
        self._current_val += self._step_val
        if self._current_val >= self._target:
            self._current_val = self._target
            self._timer.stop()
        self._value_label.setText(str(int(self._current_val)))

    def enterEvent(self, event):
        self._is_hovered = True
        accent_css = f"border-left: 4px solid {self._accent};" if self._accent else ""
        bg = _dark_or_light(
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(55,65,81,0.95), stop:1 rgba(50,60,76,0.88))",
            GLASS_HOVER_GLOW,
        )
        border = _dark_or_light("rgba(59, 130, 246, 0.35)", "rgba(37, 99, 235, 0.25)")
        self.setStyleSheet(f"""
            QFrame#glassCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 14px;
                {accent_css}
            }}
        """)
        if self._original_geometry is None:
            self._original_geometry = self.geometry()
            g = self.geometry()
            self._anim = QPropertyAnimation(self, b"geometry")
            self._anim.setDuration(150)
            self._anim.setStartValue(g)
            self._anim.setEndValue(g.adjusted(0, -2, 0, 0))
            self._anim.setEasingCurve(QEasingCurve.OutCubic)
            self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        self._setup_style()
        if self._original_geometry is not None:
            g = self.geometry()
            self._anim = QPropertyAnimation(self, b"geometry")
            self._anim.setDuration(200)
            self._anim.setStartValue(g)
            self._anim.setEndValue(self._original_geometry)
            self._anim.setEasingCurve(QEasingCurve.OutCubic)
            self._anim.start()
            self._original_geometry = None
        super().leaveEvent(event)


# ---------------------------------------------------------------------------
# Glass Section Container
# ---------------------------------------------------------------------------

class GlassSection(QFrame):
    """A frosted glass section container with optional title."""

    def __init__(
        self,
        title: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("glassSection")
        bg = _dark_or_light(
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(31,41,55,0.92), stop:1 rgba(28,37,50,0.85))",
            GLASS_FROSTED_MEDIUM,
        )
        border = _dark_or_light("rgba(55, 65, 81, 0.5)", "rgba(200, 210, 230, 0.5)")
        self.setStyleSheet(f"""
            QFrame#glassSection {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 14px;
            }}
        """)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(20, 16, 20, 20)
        self._lay.setSpacing(12)

        if title:
            t = QLabel(title)
            t.setObjectName("dashSectionTitle")
            self._lay.addWidget(t)

    def add_widget(self, widget: QWidget):
        self._lay.addWidget(widget)

    def add_layout(self, layout):
        self._lay.addLayout(layout)


# ---------------------------------------------------------------------------
# Legacy helpers (backward-compatible)
# ---------------------------------------------------------------------------

def stat_card(title: str, value: str, accent: str = PRIMARY) -> QFrame:
    """Create a stat card (legacy helper — now uses GlassCard)."""
    card = GlassCard(accent=accent)
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
    w = GlassCard()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(24, 40, 24, 40)
    lay.setAlignment(Qt.AlignCenter)
    lay.setSpacing(8)
    icon = QLabel("\U0001F4CB")
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
    """Create a glass card with title (legacy helper)."""
    c = GlassCard()
    v = QVBoxLayout(c)
    v.setContentsMargins(16, 16, 16, 16)
    v.setSpacing(12)
    t = QLabel(title)
    t.setObjectName("cardTitle")
    v.addWidget(t)
    if widget is not None:
        v.addWidget(widget)
    return c

"""Base page with lazy loading hook."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget


class BasePage(QWidget):
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._loaded = False

    def on_show(self):
        """Called each time the page becomes visible.

        Calls ``on_first_show`` once on the first visit (one-time setup), then
        calls ``refresh`` every subsequent visit so data (profile, lists, etc.)
        is always up to date — mirroring how web pages reload on navigation.
        """
        if not self._loaded:
            self.on_first_show()
            self._loaded = True
        else:
            try:
                self.refresh()
            except Exception:  # noqa: BLE001, S110
                pass

    def on_first_show(self):
        pass

    def refresh(self):
        pass

    def show_toast(self, message, kind="info"):
        if self.main_window is not None:
            self.main_window.show_toast(message, kind)

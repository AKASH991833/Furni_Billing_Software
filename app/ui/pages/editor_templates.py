"""Invoice template save/load functions.

Extracted from invoice_editor.py for code organization.
These functions operate on an InvoiceEditor instance passed as ``editor``.
"""
from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.ui.widgets.common import show_toast


def save_as_template(editor) -> None:
    """Save current invoice as a template for reuse."""
    if not editor._items:
        show_toast(editor, "No items to save as template.", "info")
        return
    from PySide6.QtWidgets import QInputDialog
    name, ok = QInputDialog.getText(editor, "Save Template",
                                    "Template name:")
    if ok and name.strip():
        try:
            from app.database.database import get_session
            from app.models.models import Setting
            template_data = {
                "items": editor._items,
                "gst_enabled": editor.cb_gst.isChecked(),
                "gst_rate": editor.f_gst.value(),
            }
            session = get_session()
            try:
                setting = session.query(Setting).filter_by(
                    key=f"invoice_template_{name.strip()}").first()
                if setting:
                    setting.value = json.dumps(template_data)
                else:
                    session.add(Setting(
                        key=f"invoice_template_{name.strip()}",
                        value=json.dumps(template_data)
                    ))
                session.commit()
            finally:
                session.close()
            show_toast(editor, f"Template '{name.strip()}' saved.", "success")
        except Exception as e:  # noqa: BLE001
            show_toast(editor, f"Failed to save template: {e}", "error")


def load_template(editor) -> None:
    """Load a saved invoice template."""
    try:
        from app.database.database import get_session
        from app.models.models import Setting
        session = get_session()
        try:
            templates = session.query(Setting).filter(
                Setting.key.like("invoice_template_%")
            ).all()
            if not templates:
                show_toast(editor, "No saved templates found.", "info")
                return
            # Show selection dialog
            dlg = QDialog(editor)
            dlg.setWindowTitle("Load Template")
            dlg.setMinimumWidth(300)
            dlg_v = QVBoxLayout(dlg)
            dlg_v.addWidget(QLabel("Select a template:"))
            template_list = QComboBox()
            for t in templates:
                label = t.key.replace("invoice_template_", "")
                template_list.addItem(label, t.value)
            dlg_v.addWidget(template_list)
            btns = QHBoxLayout()
            cancel = QPushButton("Cancel")
            cancel.clicked.connect(dlg.reject)
            load_btn = QPushButton("Load")
            load_btn.setObjectName("primaryButton")
            load_btn.clicked.connect(dlg.accept)
            btns.addStretch(1)
            btns.addWidget(cancel)
            btns.addWidget(load_btn)
            dlg_v.addLayout(btns)
            if dlg.exec():
                data = json.loads(template_list.currentData())
                editor._push_undo("load template")
                editor._items = data.get("items", [])
                editor.cb_gst.setChecked(data.get("gst_enabled", True))
                editor.f_gst.setValue(data.get("gst_rate", 0))
                editor._rebuild_sections()
                editor._mark_dirty()
                show_toast(editor, "Template loaded.", "success")
        finally:
            session.close()
    except Exception as e:  # noqa: BLE001
        show_toast(editor, f"Failed to load template: {e}", "error")

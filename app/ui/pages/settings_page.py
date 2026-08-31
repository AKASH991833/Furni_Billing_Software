"""Settings / Business Profile page.

Allows editing every business detail, uploading a logo with preview,
and editing terms & conditions / signature.
"""
from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.backup_service import (
    create_backup,
    list_backups,
    restore_backup,
)
from app.services.business_service import get_profile, save_profile
from app.services import catalog_service
from app.ui.pages.base_page import BasePage
from app.ui.widgets.common import card, primary_button, show_toast
from app.utils.paths import data_dir


def _ok(s, kind="info"):
    show_toast(s, kind)


class SettingsPage(BasePage):
    def __init__(self, main_window=None, parent=None):
        super().__init__(main_window, parent)
        self._logo_path_store = None
        self._signature_path_store = None
        self._logo_original_dir = None
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        tabs = QTabWidget()
        tabs.addTab(self._business_tab(), "Business Profile")
        tabs.addTab(self._areas_tab(), "Areas & Items")
        tabs.addTab(self._backup_tab(), "Backup & Restore")
        outer.addWidget(tabs)

    # ---------- Areas & Items tab ----------
    def _areas_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(14)

        note = QLabel(
            "Areas and their related items appear as dropdown options in the invoice "
            "editor. Nothing is hardcoded \u2014 everything is stored in the database."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#6B7280;")
        v.addWidget(note)

        split = QSplitter(Qt.Horizontal)

        # Left: Areas
        area_card = card("Areas")
        self.area_list = QListWidget()
        self.area_list.currentItemChanged.connect(self._on_area_selected)
        area_card.layout().addWidget(self.area_list, 1)
        abtns = QHBoxLayout()
        b_add_area = self._tiny_btn("+ Add Area", "primaryButton")
        b_add_area.clicked.connect(self._add_area)
        b_ren_area = self._tiny_btn("Rename")
        b_ren_area.clicked.connect(self._rename_area)
        b_del_area = self._tiny_btn("Delete")
        b_del_area.clicked.connect(self._delete_area)
        abtns.addWidget(b_add_area)
        abtns.addWidget(b_ren_area)
        abtns.addWidget(b_del_area)
        abtns.addStretch(1)
        area_card.layout().addLayout(abtns)
        split.addWidget(area_card)

        # Right: items for selected area
        item_card = card("Items for selected area")
        self.item_list = QListWidget()
        self.item_list_label = QLabel("Select an area to see its items.")
        item_card.layout().addWidget(self.item_list_label)
        item_card.layout().addWidget(self.item_list, 1)
        ibtns = QHBoxLayout()
        b_add_item = self._tiny_btn("+ Add Item", "primaryButton")
        b_add_item.clicked.connect(self._add_item)
        b_ren_item = self._tiny_btn("Rename")
        b_ren_item.clicked.connect(self._rename_item)
        b_del_item = self._tiny_btn("Delete")
        b_del_item.clicked.connect(self._delete_item)
        ibtns.addWidget(b_add_item)
        ibtns.addWidget(b_ren_item)
        ibtns.addWidget(b_del_item)
        ibtns.addStretch(1)
        item_card.layout().addLayout(ibtns)
        split.addWidget(item_card)

        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        v.addWidget(split, 1)
        return w

    def _tiny_btn(self, text, object_name=None):
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        if object_name:
            b.setObjectName(object_name)
        return b

    def _reload_areas(self, select_name=None):
        self.area_list.blockSignals(True)
        self.area_list.clear()
        self._area_items = {}
        for a in catalog_service.list_areas():
            li = QListWidgetItem(a.name)
            li.setData(Qt.UserRole, a.name)
            self.area_list.addItem(li)
            self._area_items[a.name] = a
        self.area_list.blockSignals(False)
        if select_name is not None:
            for i in range(self.area_list.count()):
                if self.area_list.item(i).data(Qt.UserRole) == select_name:
                    self.area_list.setCurrentRow(i)
                    self._on_area_selected(self.area_list.item(i), None)
                    break
        elif self.area_list.count() > 0:
            self.area_list.setCurrentRow(0)
            self._on_area_selected(self.area_list.item(0), None)

    def _current_area(self) -> str:
        it = self.area_list.currentItem()
        return it.data(Qt.UserRole) if it else ""

    def _on_area_selected(self, current, _previous):
        area = current.data(Qt.UserRole) if current else ""
        self.item_list.clear()
        if not area:
            self.item_list_label.setText("Select an area to see its items.")
            return
        items = catalog_service.list_items(area)
        self.item_list_label.setText(f"{len(items)} item(s) in {area}")
        for it in items:
            li = QListWidgetItem(it.name)
            li.setData(Qt.UserRole, it.id)
            self.item_list.addItem(li)

    def _add_area(self):
        name, ok = QInputDialog.getText(self, "Add Area", "Area name (e.g. BALCONY):")
        if ok and name.strip():
            try:
                area = catalog_service.add_area(name.strip())
                self._reload_areas(select_name=area.name)
                show_toast(self, f"Area '{area.name}' added.", "success")
            except Exception as e:  # noqa: BLE001
                show_toast(self, f"Could not add area: {e}", "error")

    def _rename_area(self):
        old = self._current_area()
        if not old:
            QMessageBox.information(self, "No area", "Select an area first.")
            return
        new, ok = QInputDialog.getText(self, "Rename Area",
                                       "New name:", text=old)
        if ok and new.strip() and new.strip().upper() != old:
            if catalog_service.rename_area(old, new.strip()):
                self._reload_areas(select_name=new.strip().upper())
                show_toast(self, "Area renamed.", "success")
            else:
                show_toast(self, "Rename failed (name may already exist).", "error")

    def _delete_area(self):
        name = self._current_area()
        if not name:
            QMessageBox.information(self, "No area", "Select an area first.")
            return
        if QMessageBox.question(
                self, "Delete Area",
                f"Delete area '{name}'?\nIts saved items will also be removed.",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        if catalog_service.delete_area(name):
            self._reload_areas()
            show_toast(self, f"Area '{name}' deleted.", "success")
        else:
            show_toast(self, "Only custom (user-added) areas can be deleted.", "error")

    def _current_item(self):
        it = self.item_list.currentItem()
        return (it.data(Qt.UserRole), it.text()) if it else (None, None)

    def _add_item(self):
        area = self._current_area()
        if not area:
            QMessageBox.information(self, "No area", "Select an area first.")
            return
        name, ok = QInputDialog.getText(self, "Add Item",
                                        f"Item name for {area}:")
        if ok and name.strip():
            it = catalog_service.add_custom_item(name.strip(), area)
            self._reload_items(area, select_it=it.id)
            show_toast(self, f"Item '{it.name}' added.", "success")

    def _rename_item(self):
        it_id, it_name = self._current_item()
        area = self._current_area()
        if it_id is None:
            QMessageBox.information(self, "No item", "Select an item first.")
            return
        new, ok = QInputDialog.getText(self, "Rename Item",
                                       "New name:", text=it_name)
        if ok and new.strip() and new.strip() != it_name:
            if catalog_service.update_item(it_id, new.strip(), area):
                self._reload_items(area)
                show_toast(self, "Item updated.", "success")
            else:
                show_toast(self, "Could not update item.", "error")

    def _delete_item(self):
        it_id, it_name = self._current_item()
        area = self._current_area()
        if it_id is None:
            QMessageBox.information(self, "No item", "Select an item first.")
            return
        if QMessageBox.question(
                self, "Delete Item",
                f"Delete item '{it_name}'?",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        if catalog_service.delete_item(it_id):
            self._reload_items(area)
            show_toast(self, "Item deleted.", "success")

    def _reload_items(self, area, select_it=None):
        self.item_list.clear()
        items = catalog_service.list_items(area)
        self.item_list_label.setText(f"{len(items)} item(s) in {area}")
        for it in items:
            li = QListWidgetItem(it.name)
            li.setData(Qt.UserRole, it.id)
            self.item_list.addItem(li)
            if select_it is not None and it.id == select_it:
                self.item_list.setCurrentItem(li)

    # ---------- Business tab ----------
    def _business_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(16)

        # Logo card
        logo_card = card("Business Logo")
        logo_row = QHBoxLayout()
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(96, 96)
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setStyleSheet(
            "border: 1px dashed #CBD5E1; border-radius: 10px; background: #F8FAFC; color: #94A3B8; font-size:12px;"
        )
        self.logo_label.setText("No logo")
        logo_btns = QVBoxLayout()
        btn_upload = primary_button("Upload Logo")
        btn_upload.clicked.connect(self._upload_logo)
        btn_remove = QPushButton("Remove Logo")
        btn_remove.clicked.connect(self._remove_logo)
        logo_btns.addWidget(btn_upload)
        logo_btns.addWidget(btn_remove)
        logo_btns.addStretch(1)
        logo_row.addWidget(self.logo_label)
        logo_row.addLayout(logo_btns)
        logo_row.addStretch(1)
        logo_card.layout().addLayout(logo_row)
        v.addWidget(logo_card)

        # Details card
        details_card = card("Business Details")
        form = QFormLayout()
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self.f_business_name = QLineEdit()
        self.f_owner_name = QLineEdit()
        self.f_business_type = QLineEdit()
        self.f_mobile = QLineEdit()
        self.f_alt_mobile = QLineEdit()
        self.f_email = QLineEdit()
        self.f_address = QTextEdit()
        self.f_address.setFixedHeight(70)
        self.f_city = QLineEdit()
        self.f_state = QLineEdit()
        self.f_pincode = QLineEdit()
        self.f_gstin = QLineEdit()
        self.f_invoice_prefix = QLineEdit()
        self.f_terms = QTextEdit()
        self.f_terms.setPlaceholderText("Terms & conditions...")

        self.cb_show_gst = QCheckBox("Show GST on invoices")
        self.sp_gst_rate = QDoubleSpinBox()
        self.sp_gst_rate.setRange(0, 100)
        self.sp_gst_rate.setSuffix(" %")
        self.sp_gst_rate.setDecimals(2)

        def _lab(t):
            l = QLabel(t)
            l.setObjectName("fieldLabel")
            return l

        form.addRow(_lab("Business / Shop Name *"), self.f_business_name)
        form.addRow(_lab("Owner Name"), self.f_owner_name)
        form.addRow(_lab("Business Type"), self.f_business_type)
        form.addRow(_lab("Mobile"), self.f_mobile)
        form.addRow(_lab("Alternate Mobile"), self.f_alt_mobile)
        form.addRow(_lab("Email"), self.f_email)
        form.addRow(_lab("Address"), self.f_address)
        form.addRow(_lab("City"), self.f_city)
        form.addRow(_lab("State"), self.f_state)
        form.addRow(_lab("Pincode"), self.f_pincode)
        form.addRow(_lab("GSTIN"), self.f_gstin)
        form.addRow(_lab("Invoice Prefix"), self.f_invoice_prefix)
        form.addRow(_lab(""), self.cb_show_gst)
        form.addRow(_lab("Default GST Rate"), self.sp_gst_rate)
        form.addRow(_lab("Terms & Conditions"), self.f_terms)
        details_card.layout().addLayout(form)
        v.addWidget(details_card)

        # Save
        save_btn = primary_button("Save Settings")
        save_btn.setFixedWidth(180)
        save_btn.clicked.connect(self._save)
        v.addWidget(save_btn, alignment=Qt.AlignLeft)
        v.addStretch(1)

        scroll.setWidget(inner)
        return scroll

    # ---------- Backup tab ----------
    def _backup_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(16)

        b_card = card("Backup")
        b_row = QHBoxLayout()
        note = QLabel(
            "Backup saves all business data (customers, invoices, payments,\n"
            "settings, profile) into a single .db file. Store it somewhere safe."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#6B7280;")
        btn_backup = primary_button("Create Backup Now")
        btn_backup.clicked.connect(self._do_backup)
        b_row.addWidget(note, 1)
        b_row.addWidget(btn_backup)
        b_card.layout().addLayout(b_row)
        v.addWidget(b_card)

        r_card = card("Restore")
        r_row = QHBoxLayout()
        rnote = QLabel(
            "Restore replaces current data with a backup. The app will\n"
            "close the database, then reopen. Make sure you have a backup."
        )
        rnote.setWordWrap(True)
        rnote.setStyleSheet("color:#6B7280;")
        btn_restore = QPushButton("Restore From File...")
        btn_restore.clicked.connect(self._do_restore)
        r_row.addWidget(rnote, 1)
        r_row.addWidget(btn_restore)
        r_card.layout().addLayout(r_row)
        v.addWidget(r_card)

        l_card = card("Available Backups")
        self.backup_list = QLabel("Loading...")
        self.backup_list.setWordWrap(True)
        self.backup_list.setStyleSheet("color:#6B7280;")
        l_card.layout().addWidget(self.backup_list)
        v.addWidget(l_card)
        v.addStretch(1)
        return w

    # ---------- Logo handling ----------
    def _upload_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose Logo", "", "Images (*.png *.jpg *.jpeg *.bmp *.svg)")
        if not path:
            return
        # Copy into app data dir so the DB path stays valid after packaging.
        dest_dir = data_dir() / "media"
        dest_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(path).suffix or ".png"
        dest = dest_dir / f"logo_{uuid.uuid4().hex}{ext}"
        try:
            shutil.copyfile(path, dest)
        except OSError as e:
            show_toast(self, f"Could not copy logo: {e}", "error")
            return
        self._logo_path_store = str(dest)
        pm = QPixmap(str(dest))
        if pm.isNull() or pm.width() <= 1:
            self.logo_label.setText("Invalid image")
        else:
            self.logo_label.setText("")
            self.logo_label.setPixmap(
                pm.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _remove_logo(self):
        self._logo_path_store = None
        self.logo_label.setText("No logo")
        self.logo_label.setPixmap(QPixmap())

    # ---------- actions ----------
    def _save(self):
        name = self.f_business_name.text().strip()
        if not name:
            show_toast(self, "Business / Shop Name is required.", "error")
            return
        data = {
            "business_name": name,
            "owner_name": self.f_owner_name.text().strip(),
            "business_type": self.f_business_type.text().strip(),
            "mobile": self.f_mobile.text().strip(),
            "alternate_mobile": self.f_alt_mobile.text().strip(),
            "email": self.f_email.text().strip(),
            "address": self.f_address.toPlainText().strip(),
            "city": self.f_city.text().strip(),
            "state": self.f_state.text().strip(),
            "pincode": self.f_pincode.text().strip(),
            "gstin": self.f_gstin.text().strip(),
            "invoice_prefix": self.f_invoice_prefix.text().strip() or "INV",
            "logo_path": self._logo_path_store,
            "terms_conditions": self.f_terms.toPlainText(),
            "show_gst": self.cb_show_gst.isChecked(),
            "default_gst_rate": self.sp_gst_rate.value(),
        }
        try:
            save_profile(data)
            show_toast(self, "Settings saved successfully.", "success")
            # Refresh the header business name immediately
            if self.main_window and hasattr(self.main_window, 'header'):
                self.main_window.header.refresh_business_name()
        except Exception as e:  # noqa: BLE001
            show_toast(self, f"Failed to save: {e}", "error")

    def on_first_show(self):
        self._load_profile()
        self.refresh_backups()
        self._reload_areas()

    def _load_profile(self):
        p = get_profile()
        if p is None:
            return
        self.f_business_name.setText(p.business_name or "")
        self.f_owner_name.setText(p.owner_name or "")
        self.f_business_type.setText(p.business_type or "")
        self.f_mobile.setText(p.mobile or "")
        self.f_alt_mobile.setText(p.alternate_mobile or "")
        self.f_email.setText(p.email or "")
        self.f_address.setPlainText(p.address or "")
        self.f_city.setText(p.city or "")
        self.f_state.setText(p.state or "")
        self.f_pincode.setText(p.pincode or "")
        self.f_gstin.setText(p.gstin or "")
        self.f_invoice_prefix.setText(p.invoice_prefix or "INV")
        self.f_terms.setPlainText(p.terms_conditions or "")
        self.cb_show_gst.setChecked(bool(p.show_gst))
        try:
            self.sp_gst_rate.setValue(float(p.default_gst_rate or 0))
        except (TypeError, ValueError):
            self.sp_gst_rate.setValue(0)

        self._logo_path_store = p.logo_path
        if p.logo_path and Path(p.logo_path).exists():
            pm = QPixmap(p.logo_path)
            if not pm.isNull():
                self.logo_label.setPixmap(
                    pm.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.logo_label.setText("")

    def _do_backup(self):
        try:
            dest = create_backup()
            show_toast(self, f"Backup created:\n{dest.name}", "success")
            self.refresh_backups()
        except Exception as e:  # noqa: BLE001
            show_toast(self, f"Backup failed: {e}", "error")

    def _do_restore(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose Backup File", str(data_dir()), "Backup (*.db)")
        if not path:
            return
        if QMessageBox.question(
                self, "Restore Backup",
                "This will REPLACE all current data with the backup.\nContinue?",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            restore_backup(path)
            show_toast(self, "Backup restored successfully.", "success")
            self._load_profile()
        except Exception as e:  # noqa: BLE001
            show_toast(self, f"Restore failed: {e}", "error")
        self.refresh_backups()

    def refresh_backups(self):
        backups = list_backups()
        if not backups:
            self.backup_list.setText("No backups yet.")
            return
        lines = [f"{b.name}  ({b.stat().st_size//1024} KB)" for b in backups[:10]]
        self.backup_list.setText("\n".join(lines))

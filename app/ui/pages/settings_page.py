"""Settings / Business Profile page.

Allows editing every business detail, uploading a logo with preview,
and editing terms & conditions / signature.
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QTime, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from app.services import catalog_service, email_backup_service, license_service
from app.services.backup_service import (
    create_backup,
    list_backups,
    restore_backup,
)
from app.services.business_service import get_profile, save_profile
from app.ui.pages.base_page import BasePage
from app.ui.widgets.common import _dark_or_light, card, primary_button, show_toast
from app.utils.area_icons import get_area_icon
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

        self._tabs = QTabWidget()
        self._tabs.addTab(self._business_tab(), "Business Profile")
        self._tabs.addTab(self._areas_tab(), "Areas & Items")
        self._tabs.addTab(self._invoice_numbering_tab(), "Invoice Numbering")
        self._tabs.addTab(self._pdf_print_tab(), "PDF & Print")
        self._tabs.addTab(self._security_tab(), "Security")
        self._tabs.addTab(self._license_tab(), "License")
        self._tabs.addTab(self._backup_tab(), "Backup & Restore")
        outer.addWidget(self._tabs)

    def switch_to_tab(self, name: str):
        """Switch to a tab by keyword (e.g. 'security')."""
        tab_map = {
            "business": 0, "profile": 0,
            "areas": 1, "items": 1,
            "invoice": 2, "numbering": 2,
            "pdf": 3, "print": 3,
            "security": 4, "pin": 4, "password": 4,
            "license": 5, "activation": 5, "licence": 5,
            "backup": 6, "restore": 6,
        }
        idx = tab_map.get(name.lower(), -1)
        if idx >= 0:
            self._tabs.setCurrentIndex(idx)

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
        note.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#6B7280')};")
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
            icon = get_area_icon(a.name)
            li = QListWidgetItem(f"{icon}  {a.name}")
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
            f"border: 1px dashed {_dark_or_light('#374151', '#CBD5E1')}; border-radius: 10px; background: {_dark_or_light('#1F2937', '#F8FAFC')}; color: {_dark_or_light('#9CA3AF', '#94A3B8')}; font-size:12px;"
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

        # Signature card
        sig_card = card("Authorized Signature")
        sig_note = QLabel(
            "Upload a scanned signature image. It will appear on generated "
            "invoices above the 'Authorized Signatory' line."
        )
        sig_note.setWordWrap(True)
        sig_note.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#6B7280')}; font-size: 12px;")
        sig_card.layout().addWidget(sig_note)
        sig_row = QHBoxLayout()
        self.sig_label = QLabel()
        self.sig_label.setFixedSize(160, 50)
        self.sig_label.setAlignment(Qt.AlignCenter)
        self.sig_label.setStyleSheet(
            f"border: 1px dashed {_dark_or_light('#374151', '#CBD5E1')}; border-radius: 8px; background: {_dark_or_light('#1F2937', '#F8FAFC')};"
            f" color: {_dark_or_light('#9CA3AF', '#94A3B8')}; font-size: 11px;"
        )
        self.sig_label.setText("No signature")
        sig_btns = QVBoxLayout()
        btn_upload_sig = primary_button("Upload Signature")
        btn_upload_sig.clicked.connect(self._upload_signature)
        btn_remove_sig = QPushButton("Remove Signature")
        btn_remove_sig.clicked.connect(self._remove_signature)
        sig_btns.addWidget(btn_upload_sig)
        sig_btns.addWidget(btn_remove_sig)
        sig_btns.addStretch(1)
        sig_row.addWidget(self.sig_label)
        sig_row.addLayout(sig_btns)
        sig_row.addStretch(1)
        sig_card.layout().addLayout(sig_row)
        v.addWidget(sig_card)

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

        # Bank & UPI Details Card
        bank_card = card("Bank & UPI Payment Details (Printed on Invoices & QR Code)")
        bank_note = QLabel(
            "Enter your official bank and UPI details. A dynamic scan-and-pay UPI QR code "
            "will be automatically generated and printed on your invoices for instant client payments."
        )
        bank_note.setWordWrap(True)
        bank_note.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#6B7280')}; font-size: 12px;")
        bank_card.layout().addWidget(bank_note)

        bf = QFormLayout()
        bf.setVerticalSpacing(10)
        bf.setLabelAlignment(Qt.AlignRight)

        self.f_bank_name = QLineEdit()
        self.f_bank_name.setPlaceholderText("e.g. State Bank of India / HDFC Bank / ICICI")
        self.f_account_number = QLineEdit()
        self.f_account_number.setPlaceholderText("e.g. 50100428912345")
        self.f_ifsc_code = QLineEdit()
        self.f_ifsc_code.setPlaceholderText("e.g. SBIN0001234")
        self.f_account_holder = QLineEdit()
        self.f_account_holder.setPlaceholderText("e.g. MAHENDRA VISHWAKARMA")
        self.f_upi_id = QLineEdit()
        self.f_upi_id.setPlaceholderText("e.g. 9876543210@paytm or business@okhdfcbank")
        self.cb_upi_qr = QCheckBox("Generate & print dynamic UPI QR code on invoice")
        self.cb_upi_qr.setChecked(True)

        bf.addRow(_lab("Bank Name"), self.f_bank_name)
        bf.addRow(_lab("Account Number"), self.f_account_number)
        bf.addRow(_lab("IFSC Code"), self.f_ifsc_code)
        bf.addRow(_lab("Account Holder"), self.f_account_holder)
        bf.addRow(_lab("UPI ID / VPA"), self.f_upi_id)
        bf.addRow(_lab(""), self.cb_upi_qr)
        bank_card.layout().addLayout(bf)
        v.addWidget(bank_card)

        # ---- Invoice Defaults card ----
        defaults_card = card("Invoice Defaults (Cell Formatting)")
        desc = QLabel(
            "Set the default font family, size, and style applied to all areas "
            "and invoice cells. You can still override per-cell in the editor."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#6B7280')}; font-size: 12px;")
        defaults_card.layout().addWidget(desc)

        df = QFormLayout()
        df.setVerticalSpacing(10)
        df.setLabelAlignment(Qt.AlignRight)

        self.f_default_font = QComboBox()
        self.f_default_font.setEditable(False)
        _fonts = (
            "(System Default)", "Segoe UI", "Arial", "Times New Roman",
            "Courier New", "Verdana", "Georgia", "Trebuchet MS",
            "Comic Sans MS", "Impact", "Lucida Console",
        )
        self.f_default_font.addItems(_fonts)
        self.f_default_font.setMinimumWidth(200)

        self.sp_default_font_size = QSpinBox()
        self.sp_default_font_size.setRange(8, 24)
        self.sp_default_font_size.setValue(13)
        self.sp_default_font_size.setSuffix(" px")

        self.cb_default_bold = QCheckBox("Bold")
        self.cb_default_underline = QCheckBox("Underline")

        # Live preview label
        self._preview_label = QLabel("Preview: Sample Cell Text")
        self._preview_label.setStyleSheet(
            f"border: 1px solid {_dark_or_light('#374151', '#E5E7EB')}; border-radius: 6px; padding: 8px 14px;"
            f" background: {_dark_or_light('#1F2937', '#FAFBFC')}; font-size: 13px;"
        )

        df.addRow(_lab("Default Font"), self.f_default_font)
        df.addRow(_lab("Default Size"), self.sp_default_font_size)
        df.addRow(_lab("Style"), self._make_hbox(self.cb_default_bold, self.cb_default_underline))
        df.addRow(_lab("Preview"), self._preview_label)
        defaults_card.layout().addLayout(df)

        # Live-update preview when any font setting changes
        self.f_default_font.currentTextChanged.connect(self._update_font_preview)
        self.sp_default_font_size.valueChanged.connect(self._update_font_preview)
        self.cb_default_bold.toggled.connect(self._update_font_preview)
        self.cb_default_underline.toggled.connect(self._update_font_preview)

        v.addWidget(defaults_card)



        # Save
        save_btn = primary_button("Save Settings")
        save_btn.setFixedWidth(180)
        save_btn.clicked.connect(self._save)
        v.addWidget(save_btn, alignment=Qt.AlignLeft)
        v.addStretch(1)

        scroll.setWidget(inner)
        return scroll

    # ---------- Security tab ----------
    def _security_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(16)

        # Change PIN card
        pin_card = card("Change Login PIN")
        pin_desc = QLabel(
            "Change the PIN used to login to the application. "
            "PIN must be 4-6 digits."
        )
        pin_desc.setWordWrap(True)
        pin_desc.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#6B7280')}; font-size: 12px;")
        pin_card.layout().addWidget(pin_desc)

        from PySide6.QtWidgets import QLineEdit as _QLE

        self.f_current_pin = _QLE()
        self.f_current_pin.setEchoMode(_QLE.EchoMode.Password)
        self.f_current_pin.setPlaceholderText("Current PIN")
        self.f_current_pin.setMinimumHeight(38)

        self.f_new_pin = _QLE()
        self.f_new_pin.setEchoMode(_QLE.EchoMode.Password)
        self.f_new_pin.setPlaceholderText("New PIN (4-6 digits)")
        self.f_new_pin.setMaxLength(6)
        self.f_new_pin.setMinimumHeight(38)

        self.f_confirm_pin = _QLE()
        self.f_confirm_pin.setEchoMode(_QLE.EchoMode.Password)
        self.f_confirm_pin.setPlaceholderText("Confirm new PIN")
        self.f_confirm_pin.setMaxLength(6)
        self.f_confirm_pin.setMinimumHeight(38)

        from PySide6.QtWidgets import QFormLayout as _QFL
        pin_form = _QFL()
        pin_form.setVerticalSpacing(10)
        pin_form.setLabelAlignment(Qt.AlignRight)

        def _lab(t):
            l = QLabel(t)
            l.setObjectName("fieldLabel")
            return l

        pin_form.addRow(_lab("Current PIN"), self.f_current_pin)
        pin_form.addRow(_lab("New PIN"), self.f_new_pin)
        pin_form.addRow(_lab("Confirm PIN"), self.f_confirm_pin)
        pin_card.layout().addLayout(pin_form)

        btn_change_pin = primary_button("Change PIN")
        btn_change_pin.setFixedWidth(160)
        btn_change_pin.clicked.connect(self._change_pin)
        pin_card.layout().addWidget(btn_change_pin, alignment=Qt.AlignLeft)

        v.addWidget(pin_card)

        # Account info card
        info_card = card("Account Info")
        from app.services import auth_service
        user = auth_service.current_user()
        if user:
            info = QLabel(f"Logged in as: <b>{user['full_name'] or user['username']}</b>")
        else:
            info = QLabel("Not logged in")
        info.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#374151')}; font-size: 13px;")
        info_card.layout().addWidget(info)
        v.addWidget(info_card)

        v.addStretch(1)
        return w

    def _change_pin(self):
        current = self.f_current_pin.text().strip()
        new = self.f_new_pin.text().strip()
        confirm = self.f_confirm_pin.text().strip()

        if not current or not new or not confirm:
            show_toast(self, "All fields are required.", "error")
            return

        if new != confirm:
            show_toast(self, "New PIN and confirmation do not match.", "error")
            return

        if len(new) < 4 or len(new) > 6:
            show_toast(self, "PIN must be 4-6 digits.", "error")
            return

        if not new.isdigit():
            show_toast(self, "PIN must contain only digits.", "error")
            return

        from app.services import auth_service
        user = auth_service.current_user()
        if not user:
            show_toast(self, "Not logged in.", "error")
            return

        ok, msg = auth_service.change_pin(current, new)
        if ok:
            show_toast(self, msg, "success")
            self.f_current_pin.clear()
            self.f_new_pin.clear()
            self.f_confirm_pin.clear()
        else:
            show_toast(self, msg, "error")

    # ---------- License tab ----------
    def _license_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(16)

        status_card = card("License Status")
        self.license_status_badge = QLabel("Checking...")
        self.license_status_badge.setWordWrap(True)
        self.license_status_badge.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color:{_dark_or_light('#9CA3AF', '#6B7280')};"
        )
        status_card.layout().addWidget(self.license_status_badge)
        v.addWidget(status_card)

        det_card = card("License Details")
        det_form = QFormLayout()
        det_form.setVerticalSpacing(10)
        det_form.setLabelAlignment(Qt.AlignRight)
        self.license_key_label = QLabel("-")
        self.license_customer_label = QLabel("-")
        self.license_machine_label = QLabel("-")
        self.license_date_label = QLabel("-")
        det_form.addRow(self._lic_field("License Key"), self.license_key_label)
        det_form.addRow(self._lic_field("Registered To"), self.license_customer_label)
        det_form.addRow(self._lic_field("Computer ID"), self.license_machine_label)
        det_form.addRow(self._lic_field("Activated On"), self.license_date_label)
        det_card.layout().addLayout(det_form)
        v.addWidget(det_card)

        act_card = card("Manage License")
        act_note = QLabel(
            "Deactivating releases this license key so it can be used on a new "
            "computer. This computer will need the key again to reactivate."
        )
        act_note.setWordWrap(True)
        act_note.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#6B7280')}; font-size: 12px;")
        act_card.layout().addWidget(act_note)
        self.btn_deactivate_license = QPushButton("Deactivate This Computer")
        self.btn_deactivate_license.setCursor(Qt.PointingHandCursor)
        self.btn_deactivate_license.clicked.connect(self._deactivate_license)
        act_card.layout().addWidget(
            self.btn_deactivate_license, alignment=Qt.AlignLeft,
        )
        v.addWidget(act_card)

        v.addStretch(1)
        return w

    @staticmethod
    def _lic_field(text: str) -> QLabel:
        l = QLabel(text)
        l.setObjectName("fieldLabel")
        return l

    def _refresh_license_tab(self):
        try:
            status = license_service.get_license_status()
            st = status["status"]
            lic = status.get("licenses") or {}
        except Exception:  # noqa: BLE001
            self.license_status_badge.setText("Could not read license information.")
            return

        if st == license_service.STATUS_VALID:
            self.license_status_badge.setText("\u2713  Activated \u2014 Lifetime License")
            self.license_status_badge.setStyleSheet(
                "font-size: 14px; font-weight: 700; color:#16A34A;"
            )
            self.btn_deactivate_license.setEnabled(True)
        elif st == license_service.STATUS_NOT_ACTIVATED:
            remaining = license_service.trial_remaining_days()
            if remaining > 0:
                text = f"Trial Mode \u2014 {remaining} day{'s' if remaining != 1 else ''} remaining"
                color = "#F59E0B"
            else:
                text = "Not Activated"
                color = "#EF4444"
            self.license_status_badge.setText(text)
            self.license_status_badge.setStyleSheet(
                f"font-size: 14px; font-weight: 700; color:{color};"
            )
        elif st == license_service.STATUS_MACHINE_MISMATCH:
            self.license_status_badge.setText(
                "License belongs to a different computer."
            )
            self.license_status_badge.setStyleSheet(
                "font-size: 14px; font-weight: 700; color:#EF4444;"
            )
        else:
            self.license_status_badge.setText(
                "License file is invalid or tampered. Contact support."
            )
            self.license_status_badge.setStyleSheet(
                "font-size: 14px; font-weight: 700; color:#EF4444;"
            )

        self.license_key_label.setText(lic.get("license_key") or "-")
        self.license_customer_label.setText(lic.get("customer_name") or "-")
        self.license_machine_label.setText(lic.get("device_fingerprint") or "-")
        self.license_date_label.setText((lic.get("activated_at") or "-")[:10])

    def _deactivate_license(self):
        confirm = QMessageBox.question(
            self,
            "Deactivate License",
            "This will release the license key from this computer. "
            "You will need the key to activate again. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            license_service.deactivate_online()
        except license_service.LicenseError as exc:
            show_toast(self, str(exc), "error")
            return
        show_toast(self, "License deactivated.", "success")
        self._refresh_license_tab()

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
        note.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#6B7280')};")
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
        rnote.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#6B7280')};")
        btn_restore = QPushButton("Restore From File...")
        btn_restore.clicked.connect(self._do_restore)
        r_row.addWidget(rnote, 1)
        r_row.addWidget(btn_restore)
        r_card.layout().addLayout(r_row)
        v.addWidget(r_card)

        l_card = card("Available Backups")
        self.backup_list = QLabel("Loading...")
        self.backup_list.setWordWrap(True)
        self.backup_list.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#6B7280')};")
        l_card.layout().addWidget(self.backup_list)
        v.addWidget(l_card)

        e_card = card("Daily Email Backup")
        self.cb_email_backup = QCheckBox("Send a backup email every day")
        self.f_email_address = QLineEdit()
        self.f_email_address.setPlaceholderText("you@gmail.com")
        self.f_email_password = QLineEdit()
        self.f_email_password.setPlaceholderText("16-character Gmail App Password")
        self.f_email_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.t_email_time = QTimeEdit()
        self.t_email_time.setDisplayFormat("HH:mm")
        self.t_email_time.setTime(QTime(19, 0))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("", self.cb_email_backup)
        form.addRow("Gmail address", self.f_email_address)
        form.addRow("App password", self.f_email_password)
        form.addRow("Time (daily)", self.t_email_time)
        e_card.layout().addLayout(form)

        pwd_note = QLabel(
            "Use a Gmail App Password, not your normal Gmail password.\n"
            "Create one at myaccount.google.com → Security → App passwords."
        )
        pwd_note.setWordWrap(True)
        pwd_note.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#6B7280')};")
        e_card.layout().addWidget(pwd_note)

        btn_row = QHBoxLayout()
        self.btn_save_email = primary_button("Save Email Settings")
        self.btn_save_email.clicked.connect(self._save_email_backup)
        self.btn_test_email = QPushButton("Send Test Email")
        self.btn_test_email.clicked.connect(self._send_test_email)
        btn_row.addWidget(self.btn_save_email)
        btn_row.addWidget(self.btn_test_email)
        btn_row.addStretch(1)
        e_card.layout().addLayout(btn_row)

        self.l_email_status = QLabel("")
        self.l_email_status.setWordWrap(True)
        self.l_email_status.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#6B7280')};")
        e_card.layout().addWidget(self.l_email_status)
        v.addWidget(e_card)
        v.addStretch(1)
        return w

    # ---------- Invoice defaults helpers ----------
    @staticmethod
    def _make_hbox(*widgets):
        """Create a horizontal layout with the given widgets."""
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(16)
        for w in widgets:
            h.addWidget(w)
        h.addStretch(1)
        return h

    def _update_font_preview(self):
        """Update the live preview label with the selected font settings."""
        family = self.f_default_font.currentText()
        size = self.sp_default_font_size.value()
        bold = self.cb_default_bold.isChecked()
        underline = self.cb_default_underline.isChecked()
        parts = [f"font-size: {size}px;"]
        if family and family != "(System Default)":
            parts.append(f"font-family: '{family}';")
        if bold:
            parts.append("font-weight: bold;")
        if underline:
            parts.append("text-decoration: underline;")
        self._preview_label.setStyleSheet(
            f"border: 1px solid {_dark_or_light('#374151', '#E5E7EB')}; border-radius: 6px; padding: 8px 14px;"
            f" background: {_dark_or_light('#1F2937', '#FAFBFC')}; {' '.join(parts)}"
        )

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
            "signature_path": self._signature_path_store,
            "terms_conditions": self.f_terms.toPlainText(),
            "show_gst": self.cb_show_gst.isChecked(),
            "default_gst_rate": self.sp_gst_rate.value(),
            # Bank & UPI details
            "bank_name": self.f_bank_name.text().strip(),
            "account_number": self.f_account_number.text().strip(),
            "ifsc_code": self.f_ifsc_code.text().strip().upper(),
            "account_holder": self.f_account_holder.text().strip(),
            "upi_id": self.f_upi_id.text().strip(),
            "upi_qr_enabled": self.cb_upi_qr.isChecked(),
            # Invoice cell formatting defaults
            "default_font_family": self.f_default_font.currentText() if self.f_default_font.currentIndex() > 0 else "",
            "default_font_size": self.sp_default_font_size.value(),
            "default_font_bold": self.cb_default_bold.isChecked(),
            "default_font_underline": self.cb_default_underline.isChecked(),
            # Invoice numbering format
            "invoice_format": self.f_invoice_format.text().strip() or "{PREFIX}-{SEQ}",
            "invoice_sequence_digits": self.sp_seq_digits.value(),
            "next_sequence_number": self.sp_next_seq.value(),
        }
        # Validate business profile fields
        from app.utils.validators import validate_business_profile
        errors = validate_business_profile(data)
        if errors:
            show_toast(self, errors[0].message, "error")
            return
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
        self._load_email_backup_ui()
        self._reload_areas()

    def refresh(self):
        self.on_first_show()
        self._refresh_license_tab()

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

        # Load bank & UPI details
        self.f_bank_name.setText(getattr(p, "bank_name", "") or "")
        self.f_account_number.setText(getattr(p, "account_number", "") or "")
        self.f_ifsc_code.setText(getattr(p, "ifsc_code", "") or "")
        self.f_account_holder.setText(getattr(p, "account_holder", "") or "")
        self.f_upi_id.setText(getattr(p, "upi_id", "") or "")
        self.cb_upi_qr.setChecked(bool(getattr(p, "upi_qr_enabled", True)))

        # Load invoice cell formatting defaults
        font_family = getattr(p, "default_font_family", "") or ""
        if font_family:
            idx = self.f_default_font.findText(font_family)
            self.f_default_font.setCurrentIndex(max(idx, 0))
        else:
            self.f_default_font.setCurrentIndex(0)  # System Default
        self.sp_default_font_size.setValue(int(getattr(p, "default_font_size", 13) or 13))
        self.cb_default_bold.setChecked(bool(getattr(p, "default_font_bold", False)))
        self.cb_default_underline.setChecked(bool(getattr(p, "default_font_underline", False)))
        self._update_font_preview()

        # Load logo
        self._logo_path_store = p.logo_path
        if p.logo_path and Path(p.logo_path).exists():
            pm = QPixmap(p.logo_path)
            if not pm.isNull():
                self.logo_label.setPixmap(
                    pm.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.logo_label.setText("")

        # Load signature
        self._signature_path_store = getattr(p, "signature_path", None)
        if self._signature_path_store and Path(self._signature_path_store).exists():
            pm = QPixmap(self._signature_path_store)
            if not pm.isNull():
                self.sig_label.setPixmap(
                    pm.scaled(150, 45, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.sig_label.setText("")

        # Load invoice numbering format
        self.f_invoice_format.setText(getattr(p, "invoice_format", "") or "")
        self.sp_seq_digits.setValue(int(getattr(p, "invoice_sequence_digits", 4) or 4))
        self.sp_next_seq.setValue(int(getattr(p, "next_sequence_number", 1) or 1))
        self._update_seq_preview()

        # Load PDF/print settings
        # Theme
        pdf_theme = getattr(p, "pdf_theme", "colour") or "colour"
        for label, tname in self._theme_map.items():
            if tname == pdf_theme:
                idx = self.f_theme_selector.findText(label)
                if idx >= 0:
                    self.f_theme_selector.setCurrentIndex(idx)
                    self._update_theme_preview(label)
                break
        # Paper & margins
        paper_size = getattr(p, "pdf_paper_size", "A4") or "A4"
        idx = self.f_paper_size.findText(paper_size)
        self.f_paper_size.setCurrentIndex(max(idx, 0))
        self.sp_margin_top.setValue(float(getattr(p, "pdf_margin_top", 15) or 15))
        self.sp_margin_bottom.setValue(float(getattr(p, "pdf_margin_bottom", 15) or 15))
        self.sp_margin_left.setValue(float(getattr(p, "pdf_margin_left", 15) or 15))
        self.sp_margin_right.setValue(float(getattr(p, "pdf_margin_right", 15) or 15))
        # Colors
        self.f_primary_color.setText(getattr(p, "pdf_primary_color", "") or "")
        self.f_secondary_color.setText(getattr(p, "pdf_secondary_color", "") or "")
        self._update_color_preview()

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

    # ---------- Email backup handlers ----------
    def _load_email_backup_ui(self):
        cfg = email_backup_service.get_email_backup_config()
        self.cb_email_backup.setChecked(cfg["enabled"])
        self.f_email_address.setText(cfg["address"])
        self.f_email_password.setText(cfg["password"])
        if cfg["time"]:
            parsed = email_backup_service._parse_time(cfg["time"])
            if parsed:
                self.t_email_time.setTime(QTime(parsed.hour, parsed.minute))
        self._refresh_email_status()

    def _refresh_email_status(self):
        cfg = email_backup_service.get_email_backup_config()
        if not cfg["enabled"]:
            self.l_email_status.setText("Daily email backup is OFF.")
        elif cfg["last_success"]:
            self.l_email_status.setText(
                f"Last backup sent: {cfg['last_success']}"
                + (f"\nLast error: {cfg['last_error']}" if cfg["last_error"] else "")
            )
        else:
            self.l_email_status.setText(
                f"Waiting for {cfg['time']} daily (never sent yet)."
                + (f"\nLast error: {cfg['last_error']}" if cfg["last_error"] else "")
            )

    def _save_email_backup(self):
        address = self.f_email_address.text().strip()
        password = self.f_email_password.text()
        time_str = self.t_email_time.time().toString("HH:mm")
        errors = email_backup_service.save_email_backup_config(
            enabled=self.cb_email_backup.isChecked(),
            address=address,
            password=password,
            time_str=time_str,
        )
        if errors:
            for e in errors:
                show_toast(self, e, "error")
            return
        show_toast(self, "Email backup settings saved.", "success")
        self._refresh_email_status()

    def _send_test_email(self):
        address = self.f_email_address.text().strip()
        password = self.f_email_password.text()
        if not address or not password:
            show_toast(self, "Enter your Gmail address and App Password first.", "error")
            return
        self.btn_test_email.setEnabled(False)
        self.btn_test_email.setText("Sending...")
        time_str = self.t_email_time.time().toString("HH:mm")

        def _work():
            try:
                cfg = {
                    "enabled": True,
                    "address": address,
                    "password": password,
                    "time": time_str,
                    "last_sent": "",
                    "last_success": "",
                    "last_error": "",
                }
                email_backup_service.send_email_backup(cfg, keep_local=False)
                ok, err = True, ""
            except Exception as exc:  # noqa: BLE001
                ok, err = False, str(exc)

            def _done():
                self.btn_test_email.setEnabled(True)
                self.btn_test_email.setText("Send Test Email")
                if ok:
                    show_toast(self, "Test backup email sent successfully.", "success")
                else:
                    show_toast(self, f"Test failed: {err}", "error")
                self._refresh_email_status()

            QTimer.singleShot(0, _done)

        import threading
        threading.Thread(target=_work, daemon=True).start()

    # ---------- Signature handling ----------
    def _upload_signature(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose Signature Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not path:
            return
        dest_dir = data_dir() / "media"
        dest_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(path).suffix or ".png"
        dest = dest_dir / f"sig_{uuid.uuid4().hex}{ext}"
        try:
            shutil.copyfile(path, dest)
        except OSError as e:
            show_toast(self, f"Could not copy signature: {e}", "error")
            return
        self._signature_path_store = str(dest)
        pm = QPixmap(str(dest))
        if pm.isNull() or pm.width() <= 1:
            self.sig_label.setText("Invalid image")
        else:
            self.sig_label.setText("")
            self.sig_label.setPixmap(
                pm.scaled(150, 45, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

    def _remove_signature(self):
        self._signature_path_store = None
        self.sig_label.setText("No signature")
        self.sig_label.setPixmap(QPixmap())

    # ---------- Invoice Numbering tab ----------
    def _invoice_numbering_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(14)

        # Format card
        fmt_card = card("Invoice Number Format")
        fmt_desc = QLabel(
            "Configure how invoice numbers are generated. Use tokens: "
            "{PREFIX} = invoice prefix, {SEQ} = sequence number, "
            "{YEAR} = 4-digit year, {CUSTOMER} = customer slug.\n"
            "Examples: {PREFIX}-{SEQ} → INV-0001, "
            "{PREFIX}-{YEAR}-{SEQ} → INV-2026-0001, "
            "{CUSTOMER}-{PREFIX}-{YEAR}-{SEQ} → Akash-INV-2026-001"
        )
        fmt_desc.setWordWrap(True)
        fmt_desc.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#6B7280')}; font-size: 12px;")
        fmt_card.layout().addWidget(fmt_desc)

        ff = QFormLayout()
        ff.setVerticalSpacing(10)
        ff.setLabelAlignment(Qt.AlignRight)

        self.f_invoice_format = QLineEdit()
        self.f_invoice_format.setPlaceholderText("e.g. {PREFIX}-{YEAR}-{SEQ}")
        self.f_invoice_format.setMinimumWidth(300)

        self.sp_seq_digits = QSpinBox()
        self.sp_seq_digits.setRange(2, 8)
        self.sp_seq_digits.setValue(4)
        self.sp_seq_digits.setSuffix(" digits")

        self.sp_next_seq = QSpinBox()
        self.sp_next_seq.setRange(1, 999999)
        self.sp_next_seq.setValue(1)
        self.sp_next_seq.setSuffix(" (next invoice will start here)")

        # Live preview
        self._seq_preview = QLabel("")
        self._seq_preview.setStyleSheet(
            f"border: 1px solid {_dark_or_light('#374151', '#E5E7EB')}; border-radius: 6px; padding: 8px 14px;"
            f" background: {_dark_or_light('#1F2937', '#FAFBFC')}; font-size: 13px; font-weight: 600; color: {_dark_or_light('#F9FAFB', '#173560')};"
        )

        def _lab(t):
            l = QLabel(t)
            l.setObjectName("fieldLabel")
            return l

        ff.addRow(_lab("Format Template"), self.f_invoice_format)
        ff.addRow(_lab("Sequence Digits"), self.sp_seq_digits)
        ff.addRow(_lab("Next Sequence Number"), self.sp_next_seq)
        ff.addRow(_lab("Preview"), self._seq_preview)
        fmt_card.layout().addLayout(ff)

        # Live-update preview
        self.f_invoice_format.textChanged.connect(self._update_seq_preview)
        self.sp_seq_digits.valueChanged.connect(self._update_seq_preview)
        self.sp_next_seq.valueChanged.connect(self._update_seq_preview)

        v.addWidget(fmt_card)

        # Reset card
        reset_card = card("Reset Sequence")
        reset_desc = QLabel(
            "Reset the sequence counter back to the next number you specify. "
            "Use this at the start of a new financial year."
        )
        reset_desc.setWordWrap(True)
        reset_desc.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#6B7280')}; font-size: 12px;")
        reset_card.layout().addWidget(reset_desc)
        v.addWidget(reset_card)

        v.addStretch(1)
        return w

    def _update_seq_preview(self):
        """Update the live preview of the invoice number format."""
        fmt = self.f_invoice_format.text().strip() or "{PREFIX}-{SEQ}"
        digits = self.sp_seq_digits.value()
        seq = self.sp_next_seq.value()
        seq_str = str(seq).zfill(digits)
        from app.services.business_service import get_profile
        profile = get_profile()
        prefix = "INV"
        if profile and profile.invoice_prefix:
            prefix = profile.invoice_prefix.strip()
        from datetime import datetime, timezone
        year = datetime.now(tz=timezone.utc).date().year
        result = fmt.replace("{PREFIX}", prefix)
        result = result.replace("{SEQ}", seq_str)
        result = result.replace("{YEAR}", str(year))
        result = result.replace("{CUSTOMER}", "CustomerName")
        self._seq_preview.setText(f"Example: {result}")

    # ---------- PDF & Print tab ----------
    def _pdf_print_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(14)

        # ---- Theme Selector card ----
        from app.pdf.theme import THEMES
        theme_card = card("Invoice Theme / Layout Style")
        theme_desc = QLabel(
            "Choose a visual theme for generated invoice PDFs. "
            "Each theme has a unique colour palette and style. "
            "You can further customize primary/secondary colors below."
        )
        theme_desc.setWordWrap(True)
        theme_desc.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#6B7280')}; font-size: 12px;")
        theme_card.layout().addWidget(theme_desc)

        # Theme combo
        self.f_theme_selector = QComboBox()
        self.f_theme_selector.setMinimumWidth(250)
        self._theme_map = {}  # display_label -> theme_name
        for tname, t in THEMES.items():
            self.f_theme_selector.addItem(t.label)
            self._theme_map[t.label] = tname

        # Theme preview swatches (3 swatches per theme: primary, secondary, bg)
        self._theme_preview_frame = QFrame()
        self._theme_preview_frame.setStyleSheet(
            f"QFrame {{ border: 1px solid {_dark_or_light('#374151', '#E5E7EB')}; border-radius: 8px; padding: 8px; background: {_dark_or_light('#1F2937', '#FAFBFC')}; }}"
        )
        self._theme_preview_layout = QHBoxLayout(self._theme_preview_frame)
        self._theme_preview_layout.setContentsMargins(12, 8, 12, 8)
        self._theme_preview_layout.setSpacing(12)

        # Preview labels (will be populated on selection)
        self._theme_swatches = []
        for i in range(5):
            sw = QLabel("  ")
            sw.setFixedSize(40, 40)
            sw.setStyleSheet(f"border: 1px solid {_dark_or_light('#374151', '#CBD5E1')}; border-radius: 6px; background: #ccc;")
            self._theme_preview_layout.addWidget(sw)
            self._theme_swatches.append(sw)

        # Theme name label
        self._theme_name_label = QLabel("")
        self._theme_name_label.setStyleSheet(f"color:{_dark_or_light('#F9FAFB', '#374151')}; font-size: 12px; font-weight: 600;")
        self._theme_preview_layout.addWidget(self._theme_name_label)
        self._theme_preview_layout.addStretch(1)

        # Connect live preview
        self.f_theme_selector.currentTextChanged.connect(self._update_theme_preview)

        tf = QFormLayout()
        tf.setVerticalSpacing(10)
        tf.setLabelAlignment(Qt.AlignRight)

        def _lab(t):
            l = QLabel(t)
            l.setObjectName("fieldLabel")
            return l

        tf.addRow(_lab("Select Theme"), self.f_theme_selector)
        tf.addRow(_lab("Preview"), self._theme_preview_frame)
        theme_card.layout().addLayout(tf)

        # Initial preview
        self._update_theme_preview(self.f_theme_selector.currentText())

        v.addWidget(theme_card)

        # Paper & Margins card
        paper_card = card("Paper Size & Margins")
        paper_desc = QLabel(
            "Configure the paper size and margins for generated PDF invoices. "
            "Margins are in millimeters."
        )
        paper_desc.setWordWrap(True)
        paper_desc.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#6B7280')}; font-size: 12px;")
        paper_card.layout().addWidget(paper_desc)

        pf = QFormLayout()
        pf.setVerticalSpacing(10)
        pf.setLabelAlignment(Qt.AlignRight)

        self.f_paper_size = QComboBox()
        self.f_paper_size.addItems(["A4", "A5", "LETTER"])
        self.f_paper_size.setMinimumWidth(150)

        self.sp_margin_top = QDoubleSpinBox()
        self.sp_margin_top.setRange(5, 40)
        self.sp_margin_top.setValue(15)
        self.sp_margin_top.setSuffix(" mm")

        self.sp_margin_bottom = QDoubleSpinBox()
        self.sp_margin_bottom.setRange(5, 40)
        self.sp_margin_bottom.setValue(15)
        self.sp_margin_bottom.setSuffix(" mm")

        self.sp_margin_left = QDoubleSpinBox()
        self.sp_margin_left.setRange(5, 40)
        self.sp_margin_left.setValue(15)
        self.sp_margin_left.setSuffix(" mm")

        self.sp_margin_right = QDoubleSpinBox()
        self.sp_margin_right.setRange(5, 40)
        self.sp_margin_right.setValue(15)
        self.sp_margin_right.setSuffix(" mm")

        def _lab(t):
            l = QLabel(t)
            l.setObjectName("fieldLabel")
            return l

        pf.addRow(_lab("Paper Size"), self.f_paper_size)
        pf.addRow(_lab("Top Margin"), self.sp_margin_top)
        pf.addRow(_lab("Bottom Margin"), self.sp_margin_bottom)
        pf.addRow(_lab("Left Margin"), self.sp_margin_left)
        pf.addRow(_lab("Right Margin"), self.sp_margin_right)
        paper_card.layout().addLayout(pf)
        v.addWidget(paper_card)

        # Color Customization card
        color_card = card("Invoice Colors (Branding)")
        color_desc = QLabel(
            "Customize the primary and secondary colors used in generated invoices. "
            "Leave empty to use the default navy & gold theme."
        )
        color_desc.setWordWrap(True)
        color_desc.setStyleSheet(f"color:{_dark_or_light('#9CA3AF', '#6B7280')}; font-size: 12px;")
        color_card.layout().addWidget(color_desc)

        cf = QFormLayout()
        cf.setVerticalSpacing(10)
        cf.setLabelAlignment(Qt.AlignRight)

        self.f_primary_color = QLineEdit()
        self.f_primary_color.setPlaceholderText("e.g. #173560 (navy) — leave empty for default")
        self.f_primary_color.setMinimumWidth(250)

        self.f_secondary_color = QLineEdit()
        self.f_secondary_color.setPlaceholderText("e.g. #C8A24B (gold) — leave empty for default")
        self.f_secondary_color.setMinimumWidth(250)

        # Color preview swatches
        self._color_preview_primary = QLabel("  ")
        self._color_preview_primary.setFixedSize(28, 28)
        self._color_preview_primary.setStyleSheet(
            f"border: 1px solid {_dark_or_light('#374151', '#CBD5E1')}; border-radius: 4px; background: #173560;"
        )
        self._color_preview_secondary = QLabel("  ")
        self._color_preview_secondary.setFixedSize(28, 28)
        self._color_preview_secondary.setStyleSheet(
            f"border: 1px solid {_dark_or_light('#374151', '#CBD5E1')}; border-radius: 4px; background: #C8A24B;"
        )

        def _color_row(label_text, line_edit, swatch):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            row.addWidget(swatch)
            row.addWidget(line_edit, 1)
            return row

        cf.addRow(_lab("Primary Color"), _color_row("", self.f_primary_color, self._color_preview_primary))
        cf.addRow(_lab("Secondary Color"), _color_row("", self.f_secondary_color, self._color_preview_secondary))
        color_card.layout().addLayout(cf)

        # Live color preview update
        self.f_primary_color.textChanged.connect(self._update_color_preview)
        self.f_secondary_color.textChanged.connect(self._update_color_preview)

        v.addWidget(color_card)

        # Save button
        save_btn_pdf = primary_button("Save PDF & Print Settings")
        save_btn_pdf.setFixedWidth(250)
        save_btn_pdf.clicked.connect(self._save_pdf_print)
        v.addWidget(save_btn_pdf, alignment=Qt.AlignLeft)

        v.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    def _update_theme_preview(self, label_text: str):
        """Update the theme preview swatches when the user selects a theme."""
        from app.pdf.theme import THEMES
        theme_name = self._theme_map.get(label_text, "colour")
        t = THEMES.get(theme_name)
        if t is None:
            return
        colors = [t.navy, t.gold, t.grand_bg, t.thead_text if t.thead_text != '#ffffff' else t.gold_dark, t.heading_text]
        labels = ["Primary", "Secondary", "Grand BG", "Accent", "Heading"]
        for i, (sw, color) in enumerate(zip(self._theme_swatches, colors)):
            sw.setStyleSheet(
                f"border: 1px solid {_dark_or_light('#374151', '#CBD5E1')}; border-radius: 6px; background: {color};"
            )
            sw.setToolTip(f"{labels[i]}: {color}")
        self._theme_name_label.setText(t.label)

    def _update_color_preview(self):
        """Update the color swatch previews live."""
        primary = self.f_primary_color.text().strip()
        if primary and len(primary) == 7 and primary.startswith("#"):
            self._color_preview_primary.setStyleSheet(
                f"border: 1px solid {_dark_or_light('#374151', '#CBD5E1')}; border-radius: 4px; background: {primary};"
            )
        else:
            self._color_preview_primary.setStyleSheet(
                f"border: 1px solid {_dark_or_light('#374151', '#CBD5E1')}; border-radius: 4px; background: #173560;"
            )

        secondary = self.f_secondary_color.text().strip()
        if secondary and len(secondary) == 7 and secondary.startswith("#"):
            self._color_preview_secondary.setStyleSheet(
                f"border: 1px solid {_dark_or_light('#374151', '#CBD5E1')}; border-radius: 4px; background: {secondary};"
            )
        else:
            self._color_preview_secondary.setStyleSheet(
                f"border: 1px solid {_dark_or_light('#374151', '#CBD5E1')}; border-radius: 4px; background: #C8A24B;"
            )

    def _save_pdf_print(self):
        """Save PDF/print settings (paper, margins, colors, theme) separately."""
        theme_label = self.f_theme_selector.currentText()
        theme_name = self._theme_map.get(theme_label, "colour")
        data = {
            "pdf_theme": theme_name,
            "pdf_paper_size": self.f_paper_size.currentText(),
            "pdf_margin_top": self.sp_margin_top.value(),
            "pdf_margin_bottom": self.sp_margin_bottom.value(),
            "pdf_margin_left": self.sp_margin_left.value(),
            "pdf_margin_right": self.sp_margin_right.value(),
            "pdf_primary_color": self.f_primary_color.text().strip(),
            "pdf_secondary_color": self.f_secondary_color.text().strip(),
        }
        try:
            save_profile(data)
            show_toast(self, "PDF & Print settings saved.", "success")
        except Exception as e:  # noqa: BLE001
            show_toast(self, f"Failed to save: {e}", "error")

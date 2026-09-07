"""Professional desktop billing invoice editor (area-driven).

Presents each selected Area as an independent, visually prominent section
(centered navy/gold heading, its own item table, area total and a per-area
"+ Add Item in this Area" button), matching the reference desktop billing UI.

Every aspect stays data-driven:
  - Areas and their configured items come from the database (catalog_service).
  - Customer / shop / invoice data come from the DB and user input.
  - The calculation engine is the existing app.utils.calculations (untouched).

Layout (inside a scroll area for responsiveness):

  Header ........... Breadcrumb "Invoices > New Invoice" + subtitle + buttons
  Card: Invoice Details .. 4-row compact layout: InvNo|Date|Due | Cust|Site|Addr
  Card: Items & Area Entry  .. grouped toolbar; then one section per Area:
                               HALL (heading bar with TOTAL + Add Item button)
                               -> table -> (+ Add New Area footer)
  RIGHT Panel: Summary ....... Apply GST, rate, discount, Subtotal / Discount /
                               Taxable / GST / GRAND TOTAL, Amount in Words

Keyboard shortcuts:
  Enter  → move to next row / create new row at end
  Tab    → move to next field in row
  Delete → delete active row (when focused in a cell)
  Ctrl+D → duplicate row
  Ctrl+S → save invoice
"""
from __future__ import annotations

from PySide6.QtCore import QDate, QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services import (
    business_service,
    catalog_service,
    customer_service,
    invoice_service,
)
from app.services.invoice_service import peek_next_invoice_number
from app.ui.widgets.common import _dark_or_light, show_toast
from app.utils import calculations as calc
from app.utils.area_icons import get_area_icon

SYS_DELETE = "\U0001F5D1"   # 🗑 trash
SYS_EDIT = "\u270E"          # ✎ edit
SYS_RULER = "\U0001F4CF"    # 📏 measurement


def _fmt(v) -> str:
    if v is None:
        return ""
    if calc.is_number(v):
        f = float(v)
        if f == int(f):
            return str(int(f))
        return f"{f:g}"
    return str(v)


def _money(v) -> str:
    try:
        return f"\u20B9 {float(v or 0):,.2f}"
    except (TypeError, ValueError):
        return "\u20B9 0.00"


from app.ui.pages.editor_measurement import MeasurementHelper


class InvoiceEditor(QWidget):
    """Full invoice editing surface."""

    COLUMNS = ("S.N.", "DESCRIPTION / ITEM", "SIZE / MEASUREMENT", "QTY",
               "RATE (\u20B9)", "AMOUNT (\u20B9)", "ACTION")

    def __init__(self, main_window=None, invoice=None, customer_id=None,
                 on_close_callback=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.invoice = invoice
        self.on_close_callback = on_close_callback
        self._items = []          # canonical flat list of row dicts
        self._row_widgets = {}    # gi -> dict of cell widgets
        self._sections = []       # [{area, start, table, total_label, add_btn}]
        self._active_gi = -1
        self._undo_stack = []     # stack of (items_copy, description) for Ctrl+Z
        self._dirty = False       # True when there are unsaved changes
        self._clipboard = None     # copied row dict for Ctrl+C / Ctrl+V
        self._cell_formatting = {}  # {(gi, field): {bold, underline, font_size, text_color, bg_color}}
        self._selected_cells = set()  # {(gi, field)} for multi-cell font formatting
        # Debounce full recalculation while the user is typing in qty/rate/amount.
        self._recalc_timer = QTimer(self)
        self._recalc_timer.setSingleShot(True)
        self._recalc_timer.setInterval(200)
        self._recalc_timer.timeout.connect(self._recalc)
        self._build()
        self._setup_shortcuts()
        self._setup_autosave()
        self._load_invoice(invoice, customer_id)

    # ============================================================ UI build
    def _build(self):
        self.setObjectName("invoiceEditor")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 10, 20, 10)
        root.setSpacing(8)

        root.addLayout(self._build_action_bar())

        # Quick Stats Bar — always visible at top
        self.stats_bar = self._build_quick_stats_bar()
        root.addWidget(self.stats_bar)

        # Single page scroll — Invoice Details → Items (full width) → Summary
        # (full width, below all items). No fixed heights hide any content; the
        # whole page scrolls as one clearly-defined region.
        self.page_scroll = QScrollArea()
        self.page_scroll.setObjectName("editorPageScroll")
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.NoFrame)
        # No left↔right scrolling — the page always fits the window width.
        self.page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.page_container = QWidget()
        self.page_container.setObjectName("editorPageContainer")
        page = QVBoxLayout(self.page_container)
        page.setContentsMargins(0, 0, 0, 0)
        page.setSpacing(12)
        page.addWidget(self._build_header_card(), 0)
        # Customer Info Card (shown when customer selected)
        self.customer_info_card = self._build_customer_info_card()
        page.addWidget(self.customer_info_card)
        page.addWidget(self._build_items_card(), 1)
        page.addWidget(self._build_summary_panel(), 0)
        self.page_layout = page
        self.page_scroll.setWidget(self.page_container)
        root.addWidget(self.page_scroll, 1)

        # Invoice Progress Indicator
        self.progress_bar = self._build_progress_indicator()
        root.addWidget(self.progress_bar)

        self._load_customers()
        self._mark_clean()  # Starting state is clean

    # ---------------------------------------------------- keyboard shortcuts
    def _setup_shortcuts(self):
        """Register global keyboard shortcuts for the editor."""
        sc_dup = QShortcut(QKeySequence("Ctrl+D"), self)
        sc_dup.activated.connect(self._duplicate_row)
        sc_save = QShortcut(QKeySequence("Ctrl+S"), self)
        sc_save.activated.connect(lambda: self._save("SAVED"))
        sc_enter = QShortcut(QKeySequence("Ctrl+Return"), self)
        sc_enter.activated.connect(lambda: self._save("SAVED"))
        sc_del = QShortcut(QKeySequence("Delete"), self)
        sc_del.activated.connect(lambda: self._delete_row())
        sc_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        sc_undo.activated.connect(self._undo)
        # Ctrl+1..9 to switch to area by index
        for i in range(1, 10):
            sc = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
            sc.activated.connect(lambda idx=i: self._switch_to_area(idx - 1))
        # Ctrl+E to export CSV
        sc_export = QShortcut(QKeySequence("Ctrl+E"), self)
        sc_export.activated.connect(self._export_csv)

    def _switch_to_area(self, index):
        """Switch focus to the area section at the given index."""
        if 0 <= index < len(self._sections):
            sec = self._sections[index]
            if hasattr(sec, '_table') and sec._table.rowCount() > 0:
                # Focus the first description field in that area
                first_gi = getattr(sec, '_start_gi', 0)
                w = self._row_widgets.get(first_gi)
                if w:
                    w['desc'].setFocus()
                    self._active_gi = first_gi

    # ---------------------------------------------------- undo / auto-save
    def _setup_autosave(self):
        """Auto-save as draft every 60 seconds if there are unsaved changes."""
        from PySide6.QtCore import QTimer
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(60_000)  # 60 seconds
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start()

    def _autosave(self):
        """Auto-save draft only for already-saved invoices (not brand new ones).

        This prevents creating unwanted draft invoices when the user just
        opened the editor but never clicked Save.
        """
        if not self._dirty:
            return
        # Only auto-save if this invoice was already saved at least once
        if not self.invoice:
            return
        cid = self.f_customer.currentData()
        if not cid:
            return  # Can't auto-save without a customer
        try:
            self._save("DRAFT")
            self._dirty = False
            show_toast(self, "Auto-saved draft.", "info")
        except Exception:  # noqa: BLE001, S110
            pass  # Silently fail — don't interrupt the user

    def _mark_dirty(self):
        """Mark the invoice as having unsaved changes."""
        self._dirty = True
        self._update_title_indicator()

    def _mark_clean(self):
        """Mark the invoice as clean (saved)."""
        self._dirty = False
        self._update_title_indicator()

    def _update_title_indicator(self):
        """Update the title bar to show unsaved changes indicator."""
        base = self.title_label.text().rstrip(" *")
        if self._dirty:
            self.title_label.setText(base + " *")
        else:
            self.title_label.setText(base)

    def _push_undo(self, description="change"):
        """Save current state to the undo stack."""
        import copy
        self._undo_stack.append((copy.deepcopy(self._items), description))
        # Keep at most 30 undo levels
        if len(self._undo_stack) > 30:
            self._undo_stack.pop(0)

    def _undo(self):
        """Undo the last change."""
        if not self._undo_stack:
            show_toast(self, "Nothing to undo.", "info")
            return
        items, desc = self._undo_stack.pop()
        self._items = items
        self._rebuild_sections()
        self._mark_dirty()
        show_toast(self, f"Undid: {desc}", "info")

    def _show_shortcuts_help(self):
        """Show a dialog listing all keyboard shortcuts."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Keyboard Shortcuts")
        dlg.setMinimumWidth(480)
        v = QVBoxLayout(dlg)
        v.setSpacing(8)

        title = QLabel("Keyboard Shortcuts")
        title.setObjectName("dialogTitle")
        v.addWidget(title)

        shortcuts = [
            ("Enter", "Move to next row (create new row at end)"),
            ("Tab", "Move to next field in same row"),
            ("Shift+Tab", "Move to previous field in same row"),
            ("Delete", "Delete active row (when field is empty/at start)"),
            ("Ctrl+D", "Duplicate current row"),
            ("Ctrl+Z", "Undo last action"),
            ("Ctrl+C", "Copy current row"),
            ("Ctrl+V", "Paste copied row (inserts after current)"),
            ("Ctrl+Up", "Move row up"),
            ("Ctrl+Down", "Move row down"),
            ("Ctrl+S", "Save invoice"),
            ("Ctrl+Enter", "Save invoice"),
            ("Escape", "Move focus out of table"),
            ("F1", "Show this help"),
            ("Right-click", "Context menu (Duplicate, Move, Delete, Move to Area)"),
            ("Drag row", "Reorder rows within an area"),
        ]

        table = QTableWidget(len(shortcuts), 2)
        table.setHorizontalHeaderLabels(["Shortcut", "Action"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(
            "QTableWidget { background: "
            + _dark_or_light("rgba(31,41,55,0.9)", "white")
            + "; alternate-background-color: "
            + _dark_or_light("rgba(40,53,72,0.6)", "#F6F8FC")
            + "; border: 1px solid "
            + _dark_or_light("#374151", "#E5E7EB")
            + "; border-radius: 8px; }"
            "QHeaderView::section { background: #173560; color: white; font-weight: 600;"
            " padding: 6px; border: none; }"
        )
        for i, (key, action) in enumerate(shortcuts):
            key_item = QTableWidgetItem(key)
            key_item.setFont(key_item.font())
            f = QFont()
            f.setBold(True)
            key_item.setFont(f)
            key_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(i, 0, key_item)
            table.setItem(i, 1, QTableWidgetItem(action))
        table.setRowCount(len(shortcuts))
        v.addWidget(table)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        v.addWidget(close_btn, alignment=Qt.AlignRight)

        dlg.exec()

    def _section_title(self, icon, text) -> QLabel:
        l = QLabel(f"{icon}  {text}")
        l.setObjectName("editorSectionTitle")
        return l

    def _field_label(self, text) -> QLabel:
        l = QLabel(text)
        l.setObjectName("fieldLabel")
        return l

    # --------------------------------------------------------- action bar
    def _build_action_bar(self) -> QVBoxLayout:
        bar = QVBoxLayout()
        bar.setSpacing(2)
        bar.setContentsMargins(0, 0, 0, 6)

        # top row: breadcrumb (left) + action buttons (right)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(0)
        crumb = QLabel("Invoices  \u203A  New Invoice")
        crumb.setObjectName("editorBreadcrumb")
        top.addWidget(crumb)
        top.addStretch(1)

        self.back_btn = self._btn("\u2190  Back")
        self.back_btn.setObjectName("editorBackBtn")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self._close_editor)

        btn_draft = self._btn("Save Draft")
        btn_draft.setObjectName("editorDraftBtn")
        btn_draft.clicked.connect(lambda: self._save("DRAFT"))

        btn_save = self._btn("\u2713  Save", "editorSaveBtn")
        btn_save.clicked.connect(lambda: self._save("SAVED"))

        # Payments / Advance button
        self.btn_payments = self._btn("\u20B9 Advance / Payments")
        self.btn_payments.setObjectName("editorPaymentBtn")
        self.btn_payments.setCursor(Qt.PointingHandCursor)
        self.btn_payments.clicked.connect(self._open_payments)

        # WhatsApp share button (visible only after invoice is saved)
        self.btn_whatsapp = self._btn("\uD83D\uDCAC WhatsApp")
        self.btn_whatsapp.setObjectName("whatsappBtn")
        self.btn_whatsapp.clicked.connect(self._share_whatsapp)
        self.btn_whatsapp.setVisible(False)

        # Print button
        self.btn_print_direct = self._btn("\uD83D\uDDA8 Print")
        self.btn_print_direct.clicked.connect(self._print_direct)
        self.btn_print_direct.setVisible(False)

        top.addWidget(self.back_btn)
        top.addSpacing(8)
        top.addWidget(btn_draft)
        top.addSpacing(6)
        top.addWidget(btn_save)
        top.addSpacing(8)
        top.addWidget(self.btn_payments)
        top.addSpacing(8)
        top.addWidget(self.btn_whatsapp)
        top.addSpacing(6)
        top.addWidget(self.btn_print_direct)
        bar.addLayout(top)

        # title row (with unsaved indicator)
        self.title_label = QLabel("New Invoice")
        self.title_label.setObjectName("editorTitle")
        bar.addWidget(self.title_label)

        # override crumb text on edit
        self.crumb_label = crumb
        return bar

    # ========================= PART A: Invoice Details — ultra-compact strip
    def _build_header_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("editorSection")
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(6)

        # Create fields first
        self.f_invoice_no = QLineEdit()
        self.f_invoice_no.setReadOnly(True)
        self.f_date = QDateEdit(QDate.currentDate())
        self.f_date.setCalendarPopup(True)
        self.f_due = QDateEdit(QDate.currentDate().addDays(7))
        self.f_due.setCalendarPopup(True)

        self.f_customer = QComboBox()
        self.f_customer.setEditable(True)
        self.f_customer.setInsertPolicy(QComboBox.NoInsert)
        self.f_customer.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.f_customer.setMinimumContentsLength(14)
        self.f_customer.setMinimumWidth(200)
        self.f_customer.completer().setFilterMode(Qt.MatchContains)
        self.f_customer.completer().setCaseSensitivity(Qt.CaseInsensitive)
        self.f_customer.currentIndexChanged.connect(self._on_customer_changed)
        self.f_customer.lineEdit().setPlaceholderText("Search by name or mobile...")
        self.f_customer.lineEdit().textChanged.connect(self._on_customer_search)

        self.f_invoice_no.setMinimumWidth(120)
        self.f_date.setMinimumWidth(118)
        self.f_due.setMinimumWidth(118)

        self.f_site = QLineEdit()
        self.f_site.setPlaceholderText("Project / Site name")
        self.f_site_addr = QLineEdit()
        self.f_site_addr.setPlaceholderText("Street, city, state, pincode")
        self.f_notes = QLineEdit()
        self.f_notes.setPlaceholderText("Internal notes (not on PDF)")

        # Helper: label + input stacked tightly
        def _field(label_text, widget):
            pair = QVBoxLayout()
            pair.setSpacing(1)
            pair.setContentsMargins(0, 0, 0, 0)
            lbl = self._field_label(label_text)
            pair.addWidget(lbl)
            pair.addWidget(widget)
            return pair

        # Payment terms dropdown + Due date with presets
        due_box = QVBoxLayout()
        due_box.setSpacing(1)
        due_box.setContentsMargins(0, 0, 0, 0)
        due_box.addWidget(self._field_label("PAYMENT TERMS"))
        due_row = QHBoxLayout()
        due_row.setSpacing(3)
        self.f_payment_terms = QComboBox()
        self.f_payment_terms.addItems([
            "Due on Delivery", "Net 7", "Net 14", "Net 15",
            "Net 30", "Net 45", "Net 60", "Custom"
        ])
        self.f_payment_terms.setMinimumWidth(110)
        self.f_payment_terms.currentTextChanged.connect(self._on_payment_terms_changed)
        due_row.addWidget(self.f_payment_terms, 1)
        for days, label in [(7, "7d"), (14, "14d"), (30, "30d")]:
            btn = self._btn(label)
            btn.setObjectName("duePresetBtn")
            btn.setFixedSize(28, 20)
            btn.setStyleSheet(btn.styleSheet() + "font-size: 9px; padding: 1px;")
            btn.clicked.connect(lambda _, d=days: self._set_due_date(d))
            due_row.addWidget(btn)
        due_box.addLayout(due_row)
        # Due date row below
        due_date_box = QVBoxLayout()
        due_date_box.setSpacing(1)
        due_date_box.setContentsMargins(0, 0, 0, 0)
        due_date_box.addWidget(self._field_label("DUE DATE"))
        due_date_row = QHBoxLayout()
        due_date_row.setSpacing(3)
        due_date_row.addWidget(self.f_due, 1)
        due_date_box.addLayout(due_date_row)

        # Customer with +New button
        cust_box = QVBoxLayout()
        cust_box.setSpacing(1)
        cust_box.setContentsMargins(0, 0, 0, 0)
        cust_box.addWidget(self._field_label("CUSTOMER"))
        cust_row = QHBoxLayout()
        cust_row.setSpacing(3)
        cust_row.addWidget(self.f_customer, 1)
        btn_new_cust = self._btn("+ New")
        btn_new_cust.clicked.connect(self._new_customer)
        cust_row.addWidget(btn_new_cust)
        cust_box.addLayout(cust_row)

        # Row 1: invoice identity fields
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        row1.addLayout(_field("INV NO.", self.f_invoice_no))
        row1.addLayout(_field("DATE", self.f_date))
        row1.addLayout(due_box, 2)
        row1.addLayout(due_date_box, 1)
        row1.addStretch(1)
        v.addLayout(row1)

        # Row 2: customer + site fields
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.addLayout(cust_box, 3)
        row2.addLayout(_field("PROJECT / SITE", self.f_site), 2)
        row2.addLayout(_field("SITE ADDRESS", self.f_site_addr), 3)
        v.addLayout(row2)

        # Notes row — full width
        notes_row = QHBoxLayout()
        notes_row.setSpacing(6)
        notes_lbl = QLabel("NOTES")
        notes_lbl.setObjectName("fieldLabel")
        notes_row.addWidget(notes_lbl)
        notes_row.addWidget(self.f_notes, 1)
        v.addLayout(notes_row)

        # Customer recent invoices (shown when customer selected)
        self.customer_invoices_frame = QFrame()
        self.customer_invoices_frame.setObjectName("recentInvoicesFrame")
        self.customer_invoices_frame.setStyleSheet(
            "QFrame { border: 1px solid "
            + _dark_or_light("#374151", "#E5E7EB")
            + "; border-radius: 6px; padding: 6px; background: "
            + _dark_or_light("rgba(31,41,55,0.9)", "#FAFBFC")
            + "; }"
        )
        ci_layout = QVBoxLayout(self.customer_invoices_frame)
        ci_layout.setContentsMargins(8, 4, 8, 4)
        ci_layout.setSpacing(4)
        ci_header = QHBoxLayout()
        ci_title = QLabel("\uD83D\uDCCB Recent Invoices")
        ci_title.setStyleSheet("font-weight: 600; color: " + _dark_or_light("#F9FAFB", "#374151") + "; font-size: 11px;")
        ci_header.addWidget(ci_title)
        ci_header.addStretch(1)
        ci_layout.addLayout(ci_header)
        self.customer_invoices_label = QLabel("Select a customer to see recent invoices.")
        self.customer_invoices_label.setStyleSheet("color: " + _dark_or_light("#9CA3AF", "#6B7280") + "; font-size: 11px;")
        self.customer_invoices_label.setWordWrap(True)
        ci_layout.addWidget(self.customer_invoices_label)
        self.customer_invoices_frame.setVisible(False)
        v.addWidget(self.customer_invoices_frame)

        return card

    def _build_quick_stats_bar(self) -> QFrame:
        """Build a quick stats bar showing key metrics at a glance."""
        bar = QFrame()
        bar.setObjectName("quickStatsBar")
        bar.setStyleSheet(
            "QFrame#quickStatsBar { background: "
            + _dark_or_light("rgba(31,41,55,0.9)", "rgba(23, 53, 96, 0.05)")
            + "; border: 1px solid "
            + _dark_or_light("rgba(75,85,99,0.5)", "rgba(200, 210, 230, 0.4)")
            + "; border-radius: 8px;"
            " padding: 4px 12px; }"
        )
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 6, 12, 6)
        h.setSpacing(20)

        def stat_widget(label, default="0"):
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            val = QLabel(default)
            val.setObjectName("quickStatValue")
            val.setStyleSheet("font-size: 16px; font-weight: 800; color: " + _dark_or_light("#F9FAFB", "#173560") + ";")
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 9px; color: " + _dark_or_light("#9CA3AF", "#6B7280") + "; font-weight: 600; letter-spacing: 0.5px;")
            lay.addWidget(val)
            lay.addWidget(lbl)
            return w, val

        self._stat_areas, self._stat_areas_val = stat_widget("AREAS")
        self._stat_items, self._stat_items_val = stat_widget("ITEMS")
        self._stat_subtotal, self._stat_subtotal_val = stat_widget("SUBTOTAL")
        self._stat_gst, self._stat_gst_val = stat_widget("GST")
        self._stat_total, self._stat_total_val = stat_widget("TOTAL", "\u20B9 0")

        # Separator
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setFixedHeight(28)
        sep.setStyleSheet("background: " + _dark_or_light("rgba(75,85,99,0.5)", "rgba(200, 210, 230, 0.5)") + ";")

        h.addWidget(self._stat_areas)
        h.addWidget(self._stat_items)
        h.addWidget(sep)
        h.addWidget(self._stat_subtotal)
        h.addWidget(self._stat_gst)
        h.addWidget(self._stat_total)
        h.addStretch(1)

        return bar

    def _update_quick_stats(self, computed, totals):
        """Update the quick stats bar with current values."""
        areas = {it.get("area") for it in self._items if it.get("area")}
        self._stat_areas_val.setText(str(len(areas)))
        self._stat_items_val.setText(str(len(self._items)))
        self._stat_subtotal_val.setText(_money(totals.get("subtotal", 0)))
        self._stat_gst_val.setText(_money(totals.get("gst_amount", 0)))
        self._stat_total_val.setText(_money(totals.get("grand_total", 0)))

    def _build_customer_info_card(self) -> QFrame:
        """Build customer info card shown when customer is selected."""
        card = QFrame()
        card.setObjectName("customerInfoCard")
        card.setStyleSheet(
            "QFrame#customerInfoCard { background: "
            + _dark_or_light("rgba(31,41,55,0.9)", "rgba(239, 243, 250, 0.6)")
            + "; border: 1px solid "
            + _dark_or_light("rgba(75,85,99,0.5)", "rgba(200, 210, 230, 0.5)")
            + "; border-radius: 10px;"
            " padding: 8px; }"
        )
        card.setVisible(False)

        h = QHBoxLayout(card)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(16)

        # Customer avatar placeholder
        self._cust_avatar = QLabel("\U0001F464")
        self._cust_avatar.setStyleSheet(
            "font-size: 28px; background: "
            + _dark_or_light("#1F2937", "white")
            + "; border-radius: 20px;"
            " padding: 4px; border: 1px solid "
            + _dark_or_light("#374151", "#E5E7EB") + ";"
        )
        self._cust_avatar.setFixedSize(44, 44)
        self._cust_avatar.setAlignment(Qt.AlignCenter)
        h.addWidget(self._cust_avatar)

        # Customer details
        details = QVBoxLayout()
        details.setSpacing(2)
        self._cust_name_label = QLabel("")
        self._cust_name_label.setStyleSheet("font-size: 14px; font-weight: 700; color: " + _dark_or_light("#F9FAFB", "#173560") + ";")
        self._cust_detail_label = QLabel("")
        self._cust_detail_label.setStyleSheet("font-size: 11px; color: " + _dark_or_light("#9CA3AF", "#6B7280") + ";")
        self._cust_stats_label = QLabel("")
        self._cust_stats_label.setStyleSheet("font-size: 10px; color: #059669; font-weight: 600;")
        details.addWidget(self._cust_name_label)
        details.addWidget(self._cust_detail_label)
        details.addWidget(self._cust_stats_label)
        h.addLayout(details, 1)

        # Quick actions
        actions = QVBoxLayout()
        actions.setSpacing(4)
        btn_view_cust = self._btn("View History")
        btn_view_cust.setStyleSheet("font-size: 10px; padding: 4px 8px;")
        btn_view_cust.clicked.connect(self._view_customer_history)
        actions.addWidget(btn_view_cust)
        actions.addStretch(1)
        h.addLayout(actions)

        return card

    def _view_customer_history(self):
        """Navigate to customer page to view full history."""
        if self.main_window and hasattr(self.main_window, 'show_page'):
            self.main_window.show_page("customers")

    def _build_progress_indicator(self) -> QFrame:
        """Build invoice completion progress indicator."""
        bar = QFrame()
        bar.setObjectName("progressIndicator")
        bar.setStyleSheet(
            "QFrame#progressIndicator { background: transparent;"
            " border-top: 1px solid "
            + _dark_or_light("rgba(75,85,99,0.5)", "rgba(200, 210, 230, 0.3)")
            + ";"
            " padding: 6px 12px; }"
        )
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 4, 12, 4)
        h.setSpacing(8)

        self._progress_label = QLabel("Invoice: 0% complete")
        self._progress_label.setStyleSheet("font-size: 10px; color: " + _dark_or_light("#9CA3AF", "#6B7280") + "; font-weight: 500;")
        h.addWidget(self._progress_label)

        # Progress bar
        self._progress_bar = QFrame()
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setStyleSheet(
            "QFrame { background: " + _dark_or_light("rgba(55,65,81,0.8)", "#E5E7EB") + "; border-radius: 3px; }"
        )
        self._progress_fill = QFrame(self._progress_bar)
        self._progress_fill.setStyleSheet(
            "QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #059669, stop:1 #10B981); border-radius: 3px; }"
        )
        self._progress_fill.setGeometry(0, 0, 0, 6)
        h.addWidget(self._progress_bar, 1)

        self._progress_status = QLabel("")
        self._progress_status.setStyleSheet("font-size: 10px; font-weight: 600;")
        h.addWidget(self._progress_status)

        return bar

    def _update_progress(self):
        """Update the progress indicator based on current invoice state."""
        score = 0
        reasons = []

        # Customer selected (+30)
        if self.f_customer.currentData():
            score += 30
        else:
            reasons.append("Select customer")

        # Items added (+40)
        non_empty = [it for it in self._items if it.get("description")]
        if non_empty:
            score += min(40, len(non_empty) * 10)
            if len(non_empty) < 3:
                reasons.append(f"Add more items ({len(non_empty)}/3+)")
        else:
            reasons.append("Add items")

        # Due date set (+10)
        if self.f_due.date() != QDate.currentDate():
            score += 10

        # Notes added (+5)
        if self.f_notes.text().strip():
            score += 5

        # Terms added (+5)
        if self.f_terms.toPlainText().strip():
            score += 5

        # Site info (+10)
        if self.f_site.text().strip():
            score += 10

        # Update UI
        pct = min(100, score)
        self._progress_label.setText(f"Invoice: {pct}% complete")

        # Update fill bar width
        bar_width = self._progress_bar.width()
        fill_width = int(bar_width * pct / 100)
        self._progress_fill.setGeometry(0, 0, fill_width, 6)

        # Status text and color
        if pct >= 80:
            self._progress_status.setText("\u2705 Ready to save")
            self._progress_status.setStyleSheet("font-size: 10px; font-weight: 600; color: #059669;")
        elif pct >= 50:
            self._progress_status.setText("\u23F3 In progress")
            self._progress_status.setStyleSheet("font-size: 10px; font-weight: 600; color: #D97706;")
        else:
            self._progress_status.setText(f"\u2753 {', '.join(reasons[:2])}")
            self._progress_status.setStyleSheet("font-size: 10px; font-weight: 600; color: " + _dark_or_light("#9CA3AF", "#6B7280") + ";")

    def _btn(self, text, object_name=None) -> QPushButton:
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        if object_name:
            b.setObjectName(object_name)
        return b

    # ==================== PART B+C: Items & Area Entry — glass toolbar
    def _build_items_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("editorSection")
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(6)

        # Card header
        head = QHBoxLayout()
        head.addWidget(self._section_title("\uD83D\uDCDD", "Items & Area Entry"))
        head.addStretch(1)
        self.item_count_label = QLabel("0 items")
        self.item_count_label.setObjectName("itemCountBadge")
        head.addWidget(self.item_count_label)
        v.addLayout(head)

        # --- Toolbar with glass-style grouped buttons ---
        tb = QHBoxLayout()
        tb.setSpacing(4)
        tb.setContentsMargins(0, 0, 0, 0)

        # Group: Add
        btn_add_menu = self._btn("+ Add Item \u25BE")
        btn_add_menu.setObjectName("primaryButton")
        self.add_menu = QMenu()
        btn_add_menu.setMenu(self.add_menu)
        self._populate_add_menu()
        tb.addWidget(btn_add_menu)
        # Recent items dropdown
        btn_recent = self._btn("Recent \u25BE")
        self.recent_menu = QMenu()
        btn_recent.setMenu(self.recent_menu)
        self._populate_recent_menu()
        tb.addWidget(btn_recent)
        btn_new_area = self._btn("+ New Area")
        btn_new_area.clicked.connect(self._add_new_area)
        tb.addWidget(btn_new_area)

        tb.addWidget(self._tb_sep())

        # Group: Row operations
        btn_dup = self._btn("\uD83D\uDCCE")
        btn_dup.setToolTip("Duplicate row  (Ctrl+D)")
        btn_dup.clicked.connect(self._duplicate_row)
        btn_up = self._btn("\u25B2")
        btn_up.setToolTip("Move row up  (Ctrl+\u2191)")
        btn_up.clicked.connect(lambda: self._move(-1))
        btn_down = self._btn("\u25BC")
        btn_down.setToolTip("Move row down  (Ctrl+\u2193)")
        btn_down.clicked.connect(lambda: self._move(1))
        btn_del = self._btn("\u2715")
        btn_del.setObjectName("ghostButton")
        btn_del.setToolTip("Delete row  (Delete)")
        btn_del.clicked.connect(lambda: self._delete_row())
        tb.addWidget(btn_dup)
        tb.addWidget(btn_up)
        tb.addWidget(btn_down)
        tb.addWidget(btn_del)

        tb.addWidget(self._tb_sep())

        # Group: Tools
        btn_meas = self._btn("Measure")
        btn_meas.clicked.connect(self._measure_current)
        self.btn_meas = btn_meas
        tb.addWidget(btn_meas)
        btn_preview = self._btn("Preview PDF")
        btn_preview.clicked.connect(self._preview_pdf)
        tb.addWidget(btn_preview)

        tb.addWidget(self._tb_sep())

        # Group: Export & Templates
        btn_export = self._btn("Export CSV")
        btn_export.clicked.connect(self._export_csv)
        tb.addWidget(btn_export)
        btn_template_save = self._btn("Save Template")
        btn_template_save.clicked.connect(self._save_as_template)
        tb.addWidget(btn_template_save)
        btn_template_load = self._btn("Load Template")
        btn_template_load.clicked.connect(self._load_template)
        tb.addWidget(btn_template_load)

        tb.addStretch(1)

        # Shortcut hints
        hints = QLabel("Tab \u2192 fields  |  Ctrl+D: dup  |  Ctrl+C/V: copy/paste  |  Ctrl+\u2191\u2193: move  |  Ctrl+Z: undo  |  F1: help")
        hints.setObjectName("shortcutHint")
        hints.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        hints.setMinimumWidth(0)
        tb.addWidget(hints)

        v.addLayout(tb)

        # Area sections container — grows naturally with the number of items.
        self.areas_container = QWidget()
        self.areas_container.setStyleSheet("background: transparent;")
        self.areas_layout = QVBoxLayout(self.areas_container)
        self.areas_layout.setContentsMargins(0, 4, 4, 0)
        self.areas_layout.setSpacing(12)
        v.addWidget(self.areas_container, 1)
        return card

    def _tb_sep(self) -> QFrame:
        s = QFrame()
        s.setFixedWidth(1)
        s.setFixedHeight(24)
        s.setStyleSheet("background: " + _dark_or_light("rgba(75,85,99,0.5)", "rgba(200, 210, 230, 0.5)") + "; border-radius: 0px;")
        return s

    def _items_hint(self) -> QLabel:
        l = QLabel('Pick an Area from "+ Add Item ▾" to start  ·  Qty or Rate = LS for manual amount')
        l.setStyleSheet("color:" + _dark_or_light("#9CA3AF", "#6B7280") + "; font-size:12px;")
        return l

    def _populate_add_menu(self):
        self.add_menu.clear()
        for a in catalog_service.list_areas():
            if a.name == "+":
                continue
            act = self.add_menu.addAction(a.name)
            act.triggered.connect(lambda _, name=a.name: self._add_item_to_area(name))
        self.add_menu.addSeparator()
        nm = self.add_menu.addAction("+ Add New Area")
        nm.triggered.connect(self._add_new_area)

    def _populate_recent_menu(self):
        """Populate the recent items dropdown with recently used items."""
        self.recent_menu.clear()
        # Get unique items from current invoice
        seen = set()
        recent_items = []
        for it in reversed(self._items):
            name = it.get("description", "")
            area = it.get("area", "OTHER")
            if name and name not in seen:
                seen.add(name)
                recent_items.append((name, area))
        if not recent_items:
            act = self.recent_menu.addAction("No recent items")
            act.setEnabled(False)
            return
        for name, area in recent_items[:10]:  # Show max 10 recent items
            act = self.recent_menu.addAction(f"{name} ({area})")
            act.triggered.connect(lambda _, n=name, a=area: self._add_recent_item(n, a))

    def _add_recent_item(self, name, area):
        """Add a recently used item to the specified area."""
        self._push_undo(f"add recent item '{name}'")
        row_d = {"area": area, "description": name, "size": "",
                 "qty_raw": "", "rate_raw": "", "amount": None}
        insert_at = len(self._items)
        for gi in range(len(self._items) - 1, -1, -1):
            if self._items[gi].get("area") == area:
                insert_at = gi + 1
                break
        self._items.insert(insert_at, row_d)
        self._rebuild_from_index(insert_at)
        self._recalc()
        self._active_gi = insert_at
        self._mark_dirty()
        w = self._row_widgets.get(insert_at)
        if w:
            w["qty"].setFocus()

# ==================== PART B: Summary panel (full width, below items)
    def _build_summary_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("summaryPanel")
        v = QVBoxLayout(panel)
        v.setContentsMargins(18, 16, 18, 18)
        v.setSpacing(10)

        # Title
        title = QLabel("SUMMARY")
        title.setObjectName("summaryTitle")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        v.addSpacing(2)

        # GST + Discount row
        gd = QGridLayout()
        gd.setHorizontalSpacing(12)
        gd.setVerticalSpacing(4)
        gd.setColumnStretch(0, 0)
        gd.setColumnStretch(1, 0)
        gd.setColumnStretch(2, 1)
        gd.setColumnStretch(3, 0)
        gd.setColumnStretch(4, 1)
        self.cb_gst = QCheckBox("GST")
        self.cb_gst.setObjectName("summaryGst")
        self.cb_gst.setCursor(Qt.PointingHandCursor)
        self.cb_gst.toggled.connect(self._on_gst_toggled)
        gd.addWidget(self.cb_gst, 0, 0)

        rl = QLabel("Rate")
        rl.setObjectName("summaryFieldLabel")
        self.f_gst = QDoubleSpinBox()
        self.f_gst.setObjectName("summarySpin")
        self.f_gst.setRange(0, 100)
        self.f_gst.setDecimals(2)
        self.f_gst.setSuffix(" %")
        self.f_gst.setEnabled(False)
        self.f_gst.valueChanged.connect(self._recalc)
        gd.addWidget(rl, 0, 1)
        gd.addWidget(self.f_gst, 0, 2)

        dl = QLabel("Discount")
        dl.setObjectName("summaryFieldLabel")
        self.f_discount = QDoubleSpinBox()
        self.f_discount.setObjectName("summarySpin")
        self.f_discount.setRange(0, 1_000_000_000)
        self.f_discount.setDecimals(2)
        self.f_discount.setPrefix("\u20B9 ")
        self.f_discount.valueChanged.connect(self._recalc)
        gd.addWidget(dl, 0, 3)
        gd.addWidget(self.f_discount, 0, 4)
        v.addLayout(gd)

        # Discount quick presets
        disc_presets = QHBoxLayout()
        disc_presets.setSpacing(4)
        disc_presets.addStretch(1)
        for pct in [5, 10, 15, 20]:
            btn = self._btn(f"{pct}%")
            btn.setObjectName("discountPresetBtn")
            btn.setFixedSize(40, 24)
            btn.clicked.connect(lambda _, p=pct: self._apply_discount_pct(p))
            disc_presets.addWidget(btn)
        disc_presets.addStretch(1)
        v.addLayout(disc_presets)

        v.addSpacing(2)
        v.addWidget(self._divider())
        v.addSpacing(2)

        # Totals — four stat boxes in 2x2 grid
        stat_grid = QGridLayout()
        stat_grid.setSpacing(8)
        self.l_subtotal = self._sum_row("Subtotal")
        self.l_discount = self._sum_row("Discount")
        self.l_taxable = self._sum_row("Taxable")
        self.l_gst = self._sum_row("GST")
        for idx, sf in enumerate((self.l_subtotal, self.l_discount, self.l_taxable, self.l_gst)):
            f = QFrame()
            f.setObjectName("summaryStat")
            fl = QVBoxLayout(f)
            fl.setContentsMargins(12, 8, 12, 8)
            fl.addWidget(sf)
            sf._stat_frame = f
            stat_grid.addWidget(f, idx // 2, idx % 2)
        v.addLayout(stat_grid)

        # Grand total bar
        gt = QFrame()
        gt.setObjectName("grandTotalBar")
        gtl = QHBoxLayout(gt)
        gtl.setContentsMargins(18, 12, 18, 12)
        gl = QLabel("GRAND TOTAL")
        gl.setObjectName("grandTotalLabel")
        self.l_grand = QLabel("\u20B9 0.00")
        self.l_grand.setObjectName("grandTotalValue")
        self.l_grand.setAlignment(Qt.AlignRight)
        gtl.addWidget(gl)
        gtl.addStretch(1)
        gtl.addWidget(self.l_grand)
        v.addWidget(gt)

        # Amount in words
        self.l_words = QLabel("Zero Rupees Only")
        self.l_words.setObjectName("wordsValue")
        self.l_words.setWordWrap(True)
        self.l_words.setAlignment(Qt.AlignCenter)
        v.addWidget(self.l_words)

        # Advance & Balance Due status card
        pay_box = QFrame()
        pay_box.setObjectName("invoicePaymentBox")
        pay_box.setStyleSheet(
            "QFrame#invoicePaymentBox {"
            "  background: rgba(37, 99, 235, 0.08);"
            "  border: 1px solid rgba(37, 99, 235, 0.25);"
            "  border-radius: 10px;"
            "  padding: 6px 12px;"
            "  margin-top: 4px;"
            "}"
        )
        pay_lay = QHBoxLayout(pay_box)
        pay_lay.setContentsMargins(8, 4, 8, 4)

        adv_v = QVBoxLayout()
        adv_v.setSpacing(1)
        adv_lbl = QLabel("ADVANCE / PAID")
        adv_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #059669; text-transform: uppercase;")
        self.l_paid = QLabel("\u20B9 0.00")
        self.l_paid.setStyleSheet("font-size: 15px; font-weight: 800; color: #059669;")
        adv_v.addWidget(adv_lbl)
        adv_v.addWidget(self.l_paid)

        bal_v = QVBoxLayout()
        bal_v.setSpacing(1)
        bal_lbl = QLabel("BALANCE DUE")
        bal_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #DC2626; text-transform: uppercase;")
        self.l_balance = QLabel("\u20B9 0.00")
        self.l_balance.setStyleSheet("font-size: 15px; font-weight: 800; color: #DC2626;")
        bal_v.addWidget(bal_lbl)
        bal_v.addWidget(self.l_balance)

        self.btn_record_advance = QPushButton("+ Add Advance")
        self.btn_record_advance.setCursor(Qt.PointingHandCursor)
        self.btn_record_advance.setStyleSheet(
            "QPushButton {"
            "  background: #2563EB;"
            "  color: white;"
            "  font-weight: 700;"
            "  font-size: 12px;"
            "  border-radius: 6px;"
            "  padding: 6px 12px;"
            "}"
            "QPushButton:hover { background: #1D4ED8; }"
        )
        self.btn_record_advance.clicked.connect(self._open_payments)

        pay_lay.addLayout(adv_v, 1)
        pay_lay.addSpacing(14)
        pay_lay.addLayout(bal_v, 1)
        pay_lay.addSpacing(14)
        pay_lay.addWidget(self.btn_record_advance, 0, Qt.AlignVCenter)
        v.addWidget(pay_box)

        v.addSpacing(2)
        v.addWidget(self._divider())
        v.addSpacing(2)

        # Terms + Authorized signature (side by side, full width)
        foot = QHBoxLayout()
        foot.setSpacing(28)
        tcol = QVBoxLayout()
        tcol.setSpacing(4)
        terms_title = QLabel("TERMS & CONDITIONS")
        terms_title.setObjectName("summarySubTitle")
        self.f_terms = QTextEdit()
        self.f_terms.setObjectName("summaryTextInput")
        self.f_terms.setMinimumWidth(220)
        self.f_terms.setMaximumHeight(72)
        self.f_terms.setPlaceholderText("e.g. 50% advance, balance on delivery")
        tcol.addWidget(terms_title)
        tcol.addWidget(self.f_terms)

        scol = QVBoxLayout()
        scol.setSpacing(4)
        scol.setAlignment(Qt.AlignTop)
        sign_title = QLabel("AUTHORIZED SIGNATURE")
        sign_title.setObjectName("summarySubTitle")
        sign_line = QFrame()
        sign_line.setObjectName("signLine")
        sign_line.setFixedHeight(36)
        scol.addWidget(sign_title)
        scol.addWidget(sign_line)

        foot.addLayout(tcol, 1)
        foot.addLayout(scol, 0)
        v.addLayout(foot)

        return panel

    def _divider(self) -> QFrame:
        d = QFrame()
        d.setObjectName("summaryDivider")
        d.setFixedHeight(1)
        return d

    def _sum_row(self, label) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 3, 0, 3)
        l = QLabel(label)
        l.setObjectName("summaryRowLabel")
        val = QLabel("\u20B9 0.00")
        val.setObjectName("summaryRowValue")
        val.setAlignment(Qt.AlignRight)
        lay.addWidget(l)
        lay.addStretch(1)
        lay.addWidget(val)
        w._value_label = val
        return w

    def _sum_row_set(self, widget, value):
        widget._value_label.setText(value)

    # ============================================================ data
    def _load_customers(self):
        self.f_customer.blockSignals(True)
        self.f_customer.clear()
        self.f_customer.addItem("Select customer...", None)
        for c in customer_service.search_customers(limit=500):
            self.f_customer.addItem(f"{c.name}  ({c.mobile or 'no mobile'})", c.id)
        self.f_customer.blockSignals(False)

    def _on_customer_changed(self, index):
        cid = self.f_customer.currentData()
        if cid:
            c = customer_service.get_customer(cid)
            if c:
                self.f_site.setText(c.name + " - Project")
                self.f_site_addr.setText(c.address or "")
                # Show customer info tooltip
                info_parts = []
                if c.mobile:
                    info_parts.append(f"Mobile: {c.mobile}")
                if c.email:
                    info_parts.append(f"Email: {c.email}")
                if c.gstin:
                    info_parts.append(f"GSTIN: {c.gstin}")
                if c.city:
                    info_parts.append(f"City: {c.city}")
                self.f_customer.setToolTip("\n".join(info_parts) if info_parts else "")
                # For a NEW invoice, refresh the customer-scoped invoice number.
                if self.invoice is None:
                    self._refresh_invoice_no(c)
                # Show recent invoices for this customer
                self._show_customer_recent_invoices(cid)
                # Update customer info card
                self._update_customer_info_card(c)
        else:
            self.customer_invoices_frame.setVisible(False)
            self.customer_info_card.setVisible(False)

    def _refresh_invoice_no(self, customer=None):
        """Update the (read-only) invoice number preview for a new invoice.

        Uses the selected customer's name (scoped numbering) and the invoice
        date's year. Falls back to the bare prefix preview when no customer
        is chosen yet.
        """
        try:
            prefix = business_service.get_invoice_prefix()
            year = self.f_date.date().year() if self.f_date else None
            if customer is None:
                cid = self.f_customer.currentData()
                if cid:
                    customer = customer_service.get_customer(cid)
            if customer and getattr(customer, "name", None):
                self.f_invoice_no.setText(
                    peek_next_invoice_number(prefix, customer.name, year))
            else:
                self.f_invoice_no.setText(peek_next_invoice_number(prefix, None, year))
        except Exception:  # noqa: BLE001, S110
            pass

    def _on_customer_search(self, text):
        """Filter customer dropdown as user types in the combo box."""
        if not text:
            return
        # Only search if the text doesn't match a currently selected item exactly
        current_text = self.f_customer.currentText()
        if text == current_text:
            return
        # Search customers matching the typed text
        matches = customer_service.search_customers(text, limit=20)
        # Save current selection
        prev_id = self.f_customer.currentData()
        self.f_customer.blockSignals(True)
        self.f_customer.clear()
        self.f_customer.addItem("Select customer...", None)
        for c in matches:
            self.f_customer.addItem(f"{c.name}  ({c.mobile or 'no mobile'})", c.id)
        # Try to restore previous selection
        if prev_id:
            idx = self.f_customer.findData(prev_id)
            if idx >= 0:
                self.f_customer.setCurrentIndex(idx)
        self.f_customer.blockSignals(False)
        # Re-open the dropdown so user sees filtered results
        self.f_customer.showPopup()

    def _show_customer_recent_invoices(self, customer_id):
        """Show recent invoices for the selected customer."""
        try:
            invoices = customer_service.customer_invoices(customer_id)[:5]
            if invoices:
                lines = []
                for inv in invoices:
                    status = inv.status
                    total = float(inv.grand_total or 0)
                    paid = sum(float(p.amount or 0) for p in (inv.payments or []))
                    outstanding = max(total - paid, 0)
                    status_color = "#16A34A" if status == "PAID" else "#DC2626" if outstanding > 0 else (_dark_or_light("#9CA3AF", "#6B7280"))
                    lines.append(
                        f"<span style='color:{_dark_or_light('#F9FAFB', '#374151')};'>{inv.invoice_number}</span> "
                        f"<span style='color:{_dark_or_light('#9CA3AF', '#6B7280')};'>{inv.invoice_date.strftime('%d-%b-%Y') if inv.invoice_date else '-'}</span> "
                        f"<span style='color:{status_color}; font-weight:600;'>\u20B9{total:,.0f}</span>"
                        f"{' <span style=color:#DC2626;>\u20B9' + f'{outstanding:,.0f}' + ' pending</span>' if outstanding > 0 else ' <span style=color:#16A34A;>PAID</span>'}"
                    )
                self.customer_invoices_label.setText("<br/>".join(lines))
                self.customer_invoices_frame.setVisible(True)
            else:
                self.customer_invoices_label.setText("No previous invoices for this customer.")
                self.customer_invoices_frame.setVisible(True)
        except Exception:  # noqa: BLE001
            self.customer_invoices_frame.setVisible(False)

    def _update_customer_info_card(self, customer):
        """Update the customer info card with customer details."""
        try:
            self._cust_name_label.setText(customer.name or "Unknown")
            details = []
            if customer.mobile:
                details.append(f"\u260E {customer.mobile}")
            if customer.email:
                details.append(f"\u2709 {customer.email}")
            if customer.city:
                details.append(f"\U0001F4CD {customer.city}")
            self._cust_detail_label.setText("  ".join(details) if details else "No contact info")

            # Get customer stats
            totals = customer_service.customer_totals(customer.id)
            total_invoiced = totals.get("total_invoiced", 0)
            outstanding = totals.get("outstanding", 0)
            invoice_count = totals.get("invoice_count", 0)

            stats_parts = []
            if invoice_count > 0:
                stats_parts.append(f"{invoice_count} invoice{'s' if invoice_count != 1 else ''}")
            if total_invoiced > 0:
                stats_parts.append(f"Total: {_money(total_invoiced)}")
            if outstanding > 0:
                stats_parts.append(f"\u26A0 Outstanding: {_money(outstanding)}")
            elif total_invoiced > 0 and outstanding == 0 and invoice_count > 0:
                stats_parts.append("\u2705 All paid")
            self._cust_stats_label.setText("  |  ".join(stats_parts) if stats_parts else "New customer")

            self.customer_info_card.setVisible(True)
        except Exception:  # noqa: BLE001
            self.customer_info_card.setVisible(False)

    def _on_payment_terms_changed(self, text):
        """Update due date based on payment terms selection."""
        terms_map = {
            "Due on Delivery": 0,
            "Net 7": 7,
            "Net 14": 14,
            "Net 15": 15,
            "Net 30": 30,
            "Net 45": 45,
            "Net 60": 60,
        }
        if text in terms_map:
            self._set_due_date(terms_map[text])

    def _set_due_date(self, days):
        """Set due date to current date + days."""
        self.f_due.setDate(QDate.currentDate().addDays(days))
        self._mark_dirty()

    def _share_whatsapp(self):
        """Share invoice PDF via WhatsApp."""
        if not self.invoice:
            show_toast(self, "Save the invoice first.", "info")
            return
        try:
            from app.services.whatsapp_service import share_invoice_pdf
            profile = business_service.get_profile()
            share_invoice_pdf(
                self,
                self.invoice.id,
                self.invoice.customer.name if self.invoice.customer else "Customer",
                profile.business_name if profile else "Business",
                self.invoice.invoice_number,
                self.invoice.customer.mobile if self.invoice.customer else "",
            )
        except Exception as e:  # noqa: BLE001
            show_toast(self, f"WhatsApp share failed: {e}", "error")

    def _print_direct(self):
        """Open print dialog directly."""
        inv_id = self.get_invoice_id()
        if not inv_id:
            show_toast(self, "Save the invoice first.", "info")
            return
        try:
            from app.pdf.pdf_service import PdfPreviewDialog
            dlg = PdfPreviewDialog(inv_id, self)
            dlg._print()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Print failed", str(e))

    def _open_payments(self):
        """Open payment dialog to record advance or partial payments."""
        if not self.invoice or not getattr(self.invoice, "id", None):
            reply = QMessageBox.question(
                self, "Save Invoice First",
                "Invoice must be saved before recording an advance payment.\n\nSave this invoice now?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                return
            self._save("SAVED")

        if self.invoice and getattr(self.invoice, "id", None):
            from app.ui.pages.payment_dialog import PaymentDialog
            dlg = PaymentDialog(self.invoice, self)
            dlg.exec()
            self._recalc()
            if self.on_close_callback:
                self.on_close_callback(refresh=True)

    def _menu_qss(self) -> str:
        """Return a QMenu stylesheet."""
        return (
            "QMenu { background: white; border: 1px solid #D7DEE9; border-radius: 8px; padding: 4px; }"
            "QMenu::item { padding: 8px 20px; border-radius: 6px; font-size: 12px; }"
            "QMenu::item:selected { background: #EFF3FA; color: #173560; }"
            "QMenu::item:disabled { color: #9CA3AF; }"
            "QMenu::separator { height: 1px; background: #E5E7EB; margin: 4px 8px; }"
        )

    def _export_csv(self):
        """Export invoice items to CSV file."""
        if not self._items:
            show_toast(self, "No items to export.", "info")
            return
        try:
            from PySide6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(
                self, "Export Items to CSV", "invoice_items.csv",
                "CSV Files (*.csv)")
            if not path:
                return
            import csv
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["S.N.", "Area", "Description", "Size", "Qty", "Rate", "Amount"])
                for i, item in enumerate(self._items, 1):
                    writer.writerow([
                        i, item.get("area", ""), item.get("description", ""),
                        item.get("size", ""), item.get("qty_raw", ""),
                        item.get("rate_raw", ""), item.get("amount", ""),
                    ])
            show_toast(self, f"Exported {len(self._items)} items to {path}", "success")
        except Exception as e:  # noqa: BLE001
            show_toast(self, f"Export failed: {e}", "error")

    def _save_as_template(self):
        from app.ui.pages.editor_templates import save_as_template
        save_as_template(self)

    def _load_template(self):
        from app.ui.pages.editor_templates import load_template
        load_template(self)

    def _new_customer(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("New Customer")
        dlg.setMinimumWidth(380)
        v = QVBoxLayout(dlg)
        v.addWidget(self._field_label("CUSTOMER NAME *"))
        f_name = QLineEdit()
        v.addWidget(f_name)
        v.addWidget(self._field_label("MOBILE"))
        f_mobile = QLineEdit()
        v.addWidget(f_mobile)
        v.addWidget(self._field_label("ADDRESS"))
        f_addr = QTextEditBox()
        f_addr.setFixedHeight(60)
        v.addWidget(f_addr)
        btns = QHBoxLayout()
        btns.addStretch(1)
        c = QPushButton("Cancel"); c.clicked.connect(dlg.reject)
        ok = QPushButton("Save Customer"); ok.setObjectName("primaryButton")
        btns.addWidget(c); btns.addWidget(ok)
        v.addLayout(btns)

        def _save_new():
            name = f_name.text().strip()
            if not name:
                QMessageBox.warning(dlg, "Name required", "Customer name is required.")
                return
            try:
                nc = customer_service.add_customer({
                    "name": name,
                    "mobile": f_mobile.text().strip(),
                    "address": f_addr.toPlainText().strip(),
                })
                self._load_customers()
                dlg.accept()
                idx = self.f_customer.findData(nc.id)
                self.f_customer.setCurrentIndex(max(idx, 0))
                show_toast(self, f"Customer '{name}' added.", "success")
            except Exception as e:  # noqa: BLE001
                QMessageBox.critical(dlg, "Failed", str(e))

        ok.clicked.connect(_save_new)
        dlg.exec()

    def _load_invoice(self, invoice, customer_id):
        if invoice:
            self.invoice = invoice
            self.title_label.setText(f"Edit Invoice #{invoice.invoice_number}")
            self.crumb_label.setText("Invoices  ›  Edit Invoice")
            self.f_invoice_no.setText(invoice.invoice_number)
            if invoice.invoice_date:
                self.f_date.setDate(QDate(invoice.invoice_date.year,
                                          invoice.invoice_date.month,
                                          invoice.invoice_date.day))
            if invoice.due_date:
                self.f_due.setDate(QDate(invoice.due_date.year,
                                         invoice.due_date.month,
                                         invoice.due_date.day))
            if invoice.customer_id:
                idx = self.f_customer.findData(invoice.customer_id)
                self.f_customer.setCurrentIndex(max(idx, 0))
            self.f_site.setText(invoice.project.name if invoice.project else invoice.site_address or "")
            self.f_site_addr.setText(invoice.site_address or "")
            self.f_notes.setText(invoice.notes or "")
            # Terms come from the business profile, not per-invoice
            _profile = business_service.get_profile()
            self.f_terms.setPlainText(_profile.terms_conditions if _profile else "")
            self.f_discount.setValue(float(invoice.discount or 0))
            self.cb_gst.setChecked(bool(getattr(invoice, "gst_enabled", True)))
            self.f_gst.setValue(float(invoice.gst_rate or 0))
            self.f_gst.setEnabled(bool(getattr(invoice, "gst_enabled", True)))
            for it in invoice.items:
                self._items.append({
                    "area": it.area or "OTHER", "description": it.description or "",
                    "size": it.size or "", "qty_raw": _fmt(it.qty_raw),
                    "rate_raw": _fmt(it.rate_raw),
                    "amount": float(it.amount) if it.amount is not None else None,
                })
            self._rebuild_sections()
        else:
            self._load_profile_defaults()  # Load font defaults from settings
            profile = business_service.get_profile()
            self.cb_gst.setChecked(bool(profile and profile.show_gst))
            self.f_gst.setEnabled(bool(profile and profile.show_gst))
            self.f_gst.setValue(float(profile.default_gst_rate or 0)
                                if (profile and profile.show_gst) else 0)
            prefix = business_service.get_invoice_prefix()
            self.f_invoice_no.setText(peek_next_invoice_number(prefix))
            # Load business profile terms into the terms field
            self.f_terms.setPlainText(profile.terms_conditions if profile else "")
            if customer_id:
                idx = self.f_customer.findData(customer_id)
                self.f_customer.setCurrentIndex(max(idx, 0))
            self._add_item_to_area(None)  # start with an empty item

    # ============================================================ sections
    def _group_sections(self):
        """Return [{area, start, end}] blocks of consecutive same-area items."""
        out = []
        gi = 0
        while gi < len(self._items):
            area = self._items[gi]["area"] or "OTHER"
            start = gi
            gi += 1
            while gi < len(self._items) and (self._items[gi]["area"] or "OTHER") == area:
                gi += 1
            out.append({"area": area, "start": start, "end": gi})
        return out

    def _clear_sections(self):
        while self.areas_layout.count():
            item = self.areas_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if hasattr(self, "area_splitter") and self.area_splitter:
            self.area_splitter.deleteLater()
            self.area_splitter = None
        self._sections = []
        self._row_widgets = {}

    def _cm(self, cm: float) -> int:
        """Convert centimetres to logical pixels (96 DPI default)."""
        return max(1, round(cm * self.logicalDpiX() / 2.54))

    def _rebuild_sections(self):
        self._clear_sections()
        # Vertical splitter — every area section can be resized with the mouse.
        self.area_splitter = QSplitter(Qt.Vertical)
        self.area_splitter.setObjectName("areaSplitter")
        self.area_splitter.setChildrenCollapsible(False)
        self.area_splitter.setHandleWidth(10)
        for sec in self._group_sections():
            self.area_splitter.addWidget(self._build_section(sec))
        self.areas_layout.addWidget(self.area_splitter, 1)
        # "+ Add New Area" footer button
        btn_new_area = self._btn("+ Add New Area")
        btn_new_area.setObjectName("newAreaBtn")
        btn_new_area.clicked.connect(self._add_new_area)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn_new_area)
        row.addStretch(1)
        self.areas_layout.addLayout(row)
        self._renumber_all()
        self._recalc()
        # Update item count indicator
        count = len(self._items)
        if hasattr(self, 'item_count_label'):
            self.item_count_label.setText(f"{count} item{'s' if count != 1 else ''}")
        # Update progress
        if hasattr(self, '_update_progress'):
            self._update_progress()

    # ========================= PART B: Area section — glass depth
    def _build_section(self, sec):
        area = sec["area"]
        sec_widget = QFrame()
        sec_widget.setObjectName("areaSection")
        v = QVBoxLayout(sec_widget)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(6)

        count = sec["end"] - sec["start"]

        # Header: full-width navy/gold banner with centered, prominent area name.
        head = QFrame()
        head.setObjectName("areaBanner")
        hb = QHBoxLayout(head)
        hb.setContentsMargins(12, 6, 12, 6)
        hb.setSpacing(8)

        # Collapse/expand toggle
        collapse_btn = self._btn("\u25BE")
        collapse_btn.setObjectName("areaCollapseBtn")
        collapse_btn.setCursor(Qt.PointingHandCursor)
        collapse_btn.setFixedSize(28, 28)
        collapse_btn.setToolTip("Collapse / Expand area")
        hb.addWidget(collapse_btn, 0)

        heading = QLabel(f"{get_area_icon(area)}  {area.upper()}")
        heading.setObjectName("areaHeading")
        heading.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        badge = QLabel(f"{count} item" + ("s" if count != 1 else ""))
        badge.setObjectName("areaCountBadge")
        hb.addWidget(heading, 1)
        hb.addWidget(badge, 0)
        hb.addSpacing(4)

        add_btn = self._btn("+ Add Item")
        add_btn.setObjectName("areaAddBtn")
        add_btn.clicked.connect(lambda _, a=area: self._add_item_to_area(a))
        hb.addWidget(add_btn, 0)
        v.addWidget(head)

        # Item table
        table = QTableWidget(0, len(self.COLUMNS))
        table.setHorizontalHeaderLabels(self.COLUMNS)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # DnD support
        table.setDragEnabled(True)
        table.setAcceptDrops(True)
        table.setDropIndicatorShown(True)
        table.setDragDropMode(QAbstractItemView.InternalMove)

        hh = table.horizontalHeader()
        # DESCRIPTION stretches to fill the page width (no horizontal scroll);
        # every other column keeps its cm size and stays mouse-adjustable.
        hh.setSectionResizeMode(0, QHeaderView.Interactive)  # S.N.
        hh.setSectionResizeMode(1, QHeaderView.Stretch)      # DESCRIPTION
        hh.setSectionResizeMode(2, QHeaderView.Interactive)  # SIZE
        hh.setSectionResizeMode(3, QHeaderView.Interactive)  # QTY
        hh.setSectionResizeMode(4, QHeaderView.Interactive)  # RATE
        hh.setSectionResizeMode(5, QHeaderView.Interactive)  # AMOUNT
        hh.setSectionResizeMode(6, QHeaderView.Interactive)  # ACTION
        hh.setMinimumSectionSize(28)
        table.setColumnWidth(0, self._cm(1.0))    # S.N.      ~1 cm
        table.setColumnWidth(1, self._cm(8.0))    # DESCRIPTION ~8 cm
        table.setColumnWidth(2, self._cm(3.5))    # SIZE      ~3.5 cm
        table.setColumnWidth(3, self._cm(2.0))    # QTY       ~2 cm
        table.setColumnWidth(4, self._cm(3.0))    # RATE      ~3 cm
        table.setColumnWidth(5, self._cm(4.0))    # AMOUNT    ~4 cm
        table.setColumnWidth(6, self._cm(3.0))    # ACTION    ~3 cm
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.verticalHeader().setDefaultSectionSize(46)
        table.verticalHeader().setMinimumSectionSize(34)
        # Rows stretch to fill the table — no empty bottom band inside a section.
        table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # populate rows for this section
        for gi in range(sec["start"], sec["end"]):
            self._insert_row(table, gi)

        # Install DnD event filter on the table
        table._drag_row = -1
        table.installEventFilter(self)

        v.addWidget(table, 1)

        # Empty area warning (shown when area has 0 items)
        empty_warning = QLabel(f"\u26A0\uFE0F  No items in {area}. Click '+ Add Item' to add items.")
        empty_warning.setStyleSheet(
            "color: " + _dark_or_light("#FCD34D", "#D97706") + ";"
            " background: " + _dark_or_light("rgba(217,119,6,0.15)", "#FEF3C7") + ";"
            " border: 1px solid " + _dark_or_light("#D97706", "#FCD34D") + ";"
            " border-radius: 8px; padding: 12px; font-size: 12px; font-weight: 600;"
        )
        empty_warning.setAlignment(Qt.AlignCenter)
        empty_warning.setVisible(count == 0)
        v.addWidget(empty_warning)

        # Area total footer — shown below that area's items (not in the header).
        total_bar = QFrame()
        total_bar.setObjectName("areaTotalBar")
        total_row = QHBoxLayout(total_bar)
        total_row.setContentsMargins(12, 6, 12, 6)
        total_name = QLabel(f"{area.upper()} TOTAL")
        total_name.setObjectName("areaTotalName")
        total_value = QLabel("\u20B9 0.00")
        total_value.setObjectName("areaTotalValue")
        total_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        total_row.addWidget(total_name)
        total_row.addStretch(1)
        total_row.addWidget(total_value)
        v.addWidget(total_bar, 0)

        sec_widget._table = table
        sec_widget._total_bar = total_bar
        sec_widget._total_label = total_value
        sec_widget._add_btn = add_btn
        sec_widget._heading = heading
        sec_widget._badge = badge
        sec_widget._empty = empty_warning
        sec_widget._start_gi = sec["start"]  # global index of first item in this section
        sec_widget._collapsed = False

        # Wire up collapse/expand toggle
        def _toggle(w=sec_widget, btn=collapse_btn, tb=table, bar=total_bar, ab=add_btn):
            w._collapsed = not w._collapsed
            collapsed = w._collapsed
            tb.setVisible(not collapsed)
            bar.setVisible(not collapsed)
            ab.setVisible(not collapsed)
            btn.setText("\u25B8" if collapsed else "\u25BE")
        collapse_btn.clicked.connect(lambda *_: _toggle())

        self._sections.append(sec_widget)
        return sec_widget

    def _section_widget_by_area(self, area):
        """Return the section widget whose banner heading matches `area`, or None."""
        for sw in self._sections:
            if sw._heading.text().strip("\u2014 ").upper() == (area or "OTHER").upper():
                return sw
        return None

    def _rebuild_from_index(self, gi, area=None):
        """Incrementally refresh sections affected by an insert/delete at `gi`.

        Only the section with area `area` (and every section after it) is
        rebuilt in place; earlier sections and the live QSplitter are left
        untouched so the UI stays responsive on large invoices.

        `gi` is the global item index; `area` may be passed explicitly when the
        insert/delete leaves `self._items[gi]` pointing at another area (e.g.
        deleting the last item of an area).

        When the section structure itself changes (a brand-new area is being
        added, an area's last item was just deleted, or no sections are built
        yet), we fall back to a full ``_rebuild_sections()`` for correctness.
        """
        ranges = self._group_sections()
        if not ranges:
            self._clear_sections()
            return
        existing_areas = {sw._heading.text().strip("\u2014 ") for sw in self._sections}
        target_areas = {r["area"] for r in ranges}
        # If any area appears in multiple (non-contiguous) blocks, the simple
        # area-name → section mapping can't be trusted; do a full rebuild.
        non_contiguous = len(target_areas) != len(ranges)
        if (not self._sections
                or not getattr(self, "area_splitter", None)
                or existing_areas != target_areas
                or non_contiguous):
            self._rebuild_sections()
            return
        if area is None and 0 <= gi < len(self._items):
            area = self._items[gi].get("area", "OTHER")
        start_rebuild = area is None
        for r in ranges:
            if not start_rebuild and r["area"] == area:
                start_rebuild = True
            if start_rebuild:
                sw = self._section_widget_by_area(r["area"])
                if sw is not None:
                    self._rebuild_section_range(sw, r)
        # Reconcile: drop section widgets that no longer map to a unique
        # contiguous range (e.g. left overs from an earlier non-contiguous
        # state), so self._sections always mirrors self._group_sections().
        matched = set()
        for sw in list(self._sections):
            mark = sw._heading.text().strip("\u2014 ")
            if mark in target_areas and mark not in matched:
                matched.add(mark)
                continue
            row_keys = [g for g, w in list(self._row_widgets.items()) if w["table"] is sw._table]
            for rk in row_keys:
                del self._row_widgets[rk]
            idx = self.area_splitter.indexOf(sw)
            if idx >= 0:
                self.area_splitter.replaceWidget(idx, QWidget())
            sw.deleteLater()
            self._sections.remove(sw)
        self._renumber_all()

    def _rebuild_section_range(self, sw, r):
        """Rebuild the item table rows for one section widget from a range dict."""
        area = r["area"]
        table = sw._table
        for gi in [g for g, w in list(self._row_widgets.items()) if w["table"] is table]:
            del self._row_widgets[gi]
        table.clearContents()
        table.setRowCount(0)
        sw._start_gi = r["start"]
        for gi in range(r["start"], r["end"]):
            self._insert_row(table, gi)
        count = r["end"] - r["start"]
        sw._badge.setText(f"{count} item" + ("s" if count != 1 else ""))
        empty_label = getattr(sw, "_empty", None)
        if empty_label is not None:
            empty_label.setVisible(count == 0)
            empty_label.setText(f"\u26A0\uFE0F  No items in {area}. Click '+ Add Item' to add items.")

    def _cell(self, widget, margins=3) -> QWidget:
        """Wrap an input so it stretches to fill the table cell (avoids clipping)."""
        cell = QWidget()
        cell.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        lay = QHBoxLayout(cell)
        lay.setContentsMargins(margins, margins, margins, margins)
        lay.setSpacing(0)
        lay.addWidget(widget, 1, Qt.AlignVCenter)
        return cell

    def _insert_row(self, table, gi):
        row_d = self._items[gi]
        area = row_d.get("area") or "OTHER"
        r = table.rowCount()
        table.insertRow(r)

        sn = QTableWidgetItem(str(r + 1))
        sn.setTextAlignment(Qt.AlignCenter)
        sn.setFlags(Qt.ItemIsEnabled)
        table.setItem(r, 0, sn)

        # Description — searchable + custom (QCompleter from area items)
        desc = QLineEdit(row_d.get("description", ""))
        desc.setPlaceholderText("Select or type item...")
        desc.textChanged.connect(lambda text, g=gi: self._on_desc_changed(g, text))
        table.setCellWidget(r, 1, self._cell(make_suggestion_lineedit(desc, gi, area, self)))

        # Size + measurement button
        size = QLineEdit(row_d.get("size", ""))
        size.setPlaceholderText("e.g. 10' x 2'")
        size.textChanged.connect(lambda text, g=gi: self._on_size_changed(g, text))
        sbtn = self._row_icon(SYS_RULER, "Measurement helper for this row")
        sbtn.clicked.connect(lambda _, g=gi: self._measure_row(g))
        size_cell = QWidget()
        size_cell.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        size_lay = QHBoxLayout(size_cell)
        size_lay.setContentsMargins(3, 3, 3, 3)
        size_lay.setSpacing(4)
        size_lay.addWidget(size, 1, Qt.AlignVCenter)
        size_lay.addWidget(sbtn, 0, Qt.AlignVCenter)
        table.setCellWidget(r, 2, size_cell)

        # Qty (text: decimals / LS)
        qty = QLineEdit(_fmt(row_d.get("qty_raw")))
        qty.setPlaceholderText("Qty / LS")
        qty.setAlignment(Qt.AlignCenter)
        qty.textChanged.connect(lambda text, g=gi: self._on_qty_changed(g, text))
        table.setCellWidget(r, 3, self._cell(qty))

        # Rate (text: numbers / LS)
        rate = QLineEdit(_fmt(row_d.get("rate_raw")))
        rate.setPlaceholderText("Rate / LS")
        rate.setAlignment(Qt.AlignRight)
        rate.textChanged.connect(lambda text, g=gi: self._on_rate_changed(g, text))
        table.setCellWidget(r, 4, self._cell(rate))

        # Amount (auto for numeric; editable for LS)
        amt = QLineEdit(_fmt(row_d.get("amount")))
        amt.setPlaceholderText("Auto / manual")
        amt.setAlignment(Qt.AlignRight)
        amt.setReadOnly(calc.is_number(row_d.get("qty_raw")) and calc.is_number(row_d.get("rate_raw")))
        amt.textChanged.connect(lambda text, g=gi: self._on_amount_changed(g, text))
        table.setCellWidget(r, 5, self._cell(amt))

        # Action: Move Up / Move Down / Edit / Delete
        act_cell = QWidget()
        act_cell.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        act_lay = QHBoxLayout(act_cell)
        act_lay.setContentsMargins(2, 3, 2, 3)
        act_lay.setSpacing(1)
        act_lay.setAlignment(Qt.AlignVCenter)
        upb = self._row_icon("\u25B2", "Move row up")
        upb.clicked.connect(lambda _, g=gi: self._move(-1))
        dnb = self._row_icon("\u25BC", "Move row down")
        dnb.clicked.connect(lambda _, g=gi: self._move(1))
        ebtn = self._row_icon(SYS_EDIT, "Edit this row")
        ebtn.setObjectName("rowEditButton")
        ebtn.clicked.connect(lambda _, g=gi: self._edit_row(g))
        dbtn = self._row_icon(SYS_DELETE, "Delete this row")
        dbtn.setObjectName("rowDeleteButton")
        dbtn.clicked.connect(lambda _, g=gi: self._delete_row(g))
        upb.setFixedSize(24, 26); dnb.setFixedSize(24, 26)
        act_lay.addWidget(upb); act_lay.addWidget(dnb)
        act_lay.addWidget(ebtn); act_lay.addWidget(dbtn)
        table.setCellWidget(r, 6, act_cell)

        self._row_widgets[gi] = {
            "desc": desc, "size": size, "qty": qty, "rate": rate, "amt": amt,
            "table": table, "area": area,
        }

        # focus tracking helper
        for wid in (desc, size, qty, rate, amt):
            wid.installEventFilter(self)

        # Attach right-click formatting menu to each cell
        self._attach_cell_format_menu(desc, gi, "desc")
        self._attach_cell_format_menu(size, gi, "size")
        self._attach_cell_format_menu(qty, gi, "qty")
        self._attach_cell_format_menu(rate, gi, "rate")
        self._attach_cell_format_menu(amt, gi, "amt")
        # Re-apply any stored formatting
        self._apply_cell_fmt(desc, gi, "desc")
        self._apply_cell_fmt(size, gi, "size")
        self._apply_cell_fmt(qty, gi, "qty")
        self._apply_cell_fmt(rate, gi, "rate")
        self._apply_cell_fmt(amt, gi, "amt")

    def _row_icon(self, glyph, tip) -> QPushButton:
        b = QPushButton(glyph)
        b.setObjectName("rowIconButton")
        b.setCursor(Qt.PointingHandCursor)
        b.setToolTip(tip)
        b.setFixedSize(28, 28)
        return b

    # ===================== Cell formatting — right-click menu
    _DEFAULT_FONT_SIZE = 13

    # Available font families for the font picker
    _FONT_FAMILIES = (
        ("Segoe UI",       "Segoe UI"),
        ("Arial",          "Arial"),
        ("Times New Roman", "Times New Roman"),
        ("Courier New",    "Courier New"),
        ("Verdana",        "Verdana"),
        ("Georgia",        "Georgia"),
        ("Trebuchet MS",   "Trebuchet MS"),
        ("Comic Sans MS",  "Comic Sans MS"),
        ("Impact",         "Impact"),
        ("Lucida Console", "Lucida Console"),
    )

    def _load_profile_defaults(self):
        """Load font defaults from BusinessProfile and set _DEFAULT_FONT_SIZE."""
        profile = business_service.get_profile()
        if not profile:
            return
        # Update the class-level default font size
        self._DEFAULT_FONT_SIZE = int(getattr(profile, "default_font_size", 13) or 13)
        # Store profile defaults for new cells
        self._profile_font_family = getattr(profile, "default_font_family", "") or ""
        self._profile_font_bold = bool(getattr(profile, "default_font_bold", False))
        self._profile_font_underline = bool(getattr(profile, "default_font_underline", False))

    def _get_cell_fmt(self, gi, field):
        """Return formatting dict for a cell, creating defaults if needed.

        Uses the profile-wide font defaults (family, size, bold, underline).
        """
        key = (gi, field)
        if key not in self._cell_formatting:
            # Start with profile defaults
            family = getattr(self, "_profile_font_family", "")
            bold = getattr(self, "_profile_font_bold", False)
            underline = getattr(self, "_profile_font_underline", False)
            font_size = self._DEFAULT_FONT_SIZE

            self._cell_formatting[key] = {
                "bold": bold,
                "underline": underline,
                "font_size": font_size,
                "font_family": family,
                "text_color": "", "bg_color": "",
            }
        return self._cell_formatting[key]

    def _apply_cell_fmt(self, widget, gi, field):
        """Apply stored formatting to a QLineEdit via stylesheet."""
        fmt = self._get_cell_fmt(gi, field)
        parts = []
        parts.append(f"font-size: {fmt['font_size']}px;")
        if fmt.get("font_family"):
            parts.append(f"font-family: '{fmt['font_family']}';")
        if fmt["bold"]:
            parts.append("font-weight: bold;")
        if fmt["underline"]:
            parts.append("text-decoration: underline;")
        if fmt["text_color"]:
            parts.append(f"color: {fmt['text_color']};")
        if fmt["bg_color"]:
            parts.append(f"background: {fmt['bg_color']};")
        widget.setStyleSheet(" ".join(parts))

    def _attach_cell_format_menu(self, widget, gi, field):
        """Attach a right-click context menu for cell formatting to a QLineEdit."""
        widget.setContextMenuPolicy(Qt.CustomContextMenu)

        def _show_menu(pos):
            menu = QMenu(widget)
            menu.setStyleSheet(self._menu_qss())
            fmt = self._get_cell_fmt(gi, field)

            # --- Bold ---
            act_bold = menu.addAction(f"{'✓ ' if fmt['bold'] else '  '}Bold  (Ctrl+B)")
            act_bold.triggered.connect(lambda: self._toggle_fmt(gi, field, "bold", widget))

            # --- Underline ---
            act_ul = menu.addAction(f"{'✓ ' if fmt['underline'] else '  '}Underline  (Ctrl+U)")
            act_ul.triggered.connect(lambda: self._toggle_fmt(gi, field, "underline", widget))

            menu.addSeparator()

            # --- Font Family submenu ---
            current_family = fmt.get("font_family", "")
            fam_menu = menu.addMenu("  \U0001F4DD  Font Family")
            for label, family in self._FONT_FAMILIES:
                tick = "✓ " if current_family == family else "  "
                act_fam = fam_menu.addAction(f"{tick}{label}")
                fam_act = act_fam
                fam_act.triggered.connect(lambda _, f=family: self._set_cell_font_family(gi, field, f, widget))
            if current_family:
                fam_menu.addSeparator()
                act_fam_reset = fam_menu.addAction("  ↺  Reset Font Family")
                act_fam_reset.triggered.connect(lambda: self._set_cell_font_family(gi, field, "", widget))

            menu.addSeparator()

            # --- Font Size ---
            act_inc = menu.addAction("  🔍+  Increase Font Size")
            act_inc.triggered.connect(lambda: self._change_font_size(gi, field, +1, widget))
            act_dec = menu.addAction("  🔍−  Decrease Font Size")
            act_dec.triggered.connect(lambda: self._change_font_size(gi, field, -1, widget))
            act_reset_size = menu.addAction("  ↺  Reset to Default Size")
            act_reset_size.triggered.connect(lambda: self._reset_font_size(gi, field, widget))

            menu.addSeparator()

            # --- Text Color ---
            act_tc = menu.addAction("  🎨  Text Color")
            act_tc.triggered.connect(lambda: self._pick_color(gi, field, "text_color", widget))
            act_tc_reset = menu.addAction("  ↺  Reset Text Color")
            act_tc_reset.triggered.connect(lambda: self._reset_color(gi, field, "text_color", widget))

            menu.addSeparator()

            # --- Background Color ---
            act_bg = menu.addAction("  🖌  Background Color")
            act_bg.triggered.connect(lambda: self._pick_color(gi, field, "bg_color", widget))
            act_bg_reset = menu.addAction("  ↺  Reset Background Color")
            act_bg_reset.triggered.connect(lambda: self._reset_color(gi, field, "bg_color", widget))

            menu.addSeparator()

            # --- Reset All ---
            act_reset = menu.addAction("  ✕  Reset All Formatting")
            act_reset.triggered.connect(lambda: self._reset_all_fmt(gi, field, widget))

            menu.exec(widget.mapToGlobal(pos))

        widget.customContextMenuRequested.connect(_show_menu)

    def _toggle_fmt(self, gi, field, prop, widget):
        fmt = self._get_cell_fmt(gi, field)
        fmt[prop] = not fmt[prop]
        self._apply_cell_fmt(widget, gi, field)

    def _change_font_size(self, gi, field, delta, widget):
        fmt = self._get_cell_fmt(gi, field)
        fmt["font_size"] = max(8, min(24, fmt["font_size"] + delta))
        self._apply_cell_fmt(widget, gi, field)

    def _reset_font_size(self, gi, field, widget):
        fmt = self._get_cell_fmt(gi, field)
        fmt["font_size"] = self._DEFAULT_FONT_SIZE
        self._apply_cell_fmt(widget, gi, field)

    def _set_cell_font_family(self, gi, field, family, widget):
        """Set the font family for a single cell."""
        fmt = self._get_cell_fmt(gi, field)
        fmt["font_family"] = family
        self._apply_cell_fmt(widget, gi, field)

    def _pick_color(self, gi, field, prop, widget):
        fmt = self._get_cell_fmt(gi, field)
        current = QColor(fmt[prop]) if fmt[prop] else QColor(Qt.white)
        color = QColorDialog.getColor(current, self, "Choose Color")
        if color.isValid():
            fmt[prop] = color.name()
            self._apply_cell_fmt(widget, gi, field)

    def _reset_color(self, gi, field, prop, widget):
        fmt = self._get_cell_fmt(gi, field)
        fmt[prop] = ""
        self._apply_cell_fmt(widget, gi, field)

    def _reset_all_fmt(self, gi, field, widget):
        key = (gi, field)
        self._cell_formatting[key] = {
            "bold": False, "underline": False,
            "font_size": self._DEFAULT_FONT_SIZE,
            "font_family": "",
            "text_color": "", "bg_color": "",
        }
        widget.setStyleSheet("")

    # ===================== Multi-cell selection for bulk formatting
    _SELECTION_BORDER = "2px solid #2563EB"

    def _toggle_cell_selection(self, gi, field):
        """Toggle cell selection (Ctrl+Click). Adds/removes from selected set."""
        key = (gi, field)
        if key in self._selected_cells:
            self._selected_cells.discard(key)
        else:
            self._selected_cells.add(key)
        self._highlight_selected_cells()

    def _select_range(self, gi_start, field_start, gi_end, field_end):
        """Select a rectangular range of cells (Shift+Click)."""
        self._selected_cells.clear()
        fi_start = self._FIELD_ORDER.index(field_start) if field_start in self._FIELD_ORDER else 0
        fi_end = self._FIELD_ORDER.index(field_end) if field_end in self._FIELD_ORDER else len(self._FIELD_ORDER) - 1
        gi_s, gi_e = min(gi_start, gi_end), max(gi_start, gi_end)
        fi_s, fi_e = min(fi_start, fi_end), max(fi_start, fi_end)
        for gi in range(gi_s, gi_e + 1):
            for fi in range(fi_s, fi_e + 1):
                self._selected_cells.add((gi, self._FIELD_ORDER[fi]))
        self._highlight_selected_cells()
    
    def _select_all_cells(self):
        """Select every editable cell in the invoice."""
        self._selected_cells.clear()
        for gi in range(len(self._items)):
            for field in self._FIELD_ORDER:
                self._selected_cells.add((gi, field))
        self._highlight_selected_cells()

    def _clear_selection(self):
        """Clear all cell selections."""
        self._selected_cells.clear()
        self._highlight_selected_cells()

    def _highlight_selected_cells(self):
        """Visually highlight all selected cells with a blue border."""
        for gi, wd in self._row_widgets.items():
            for fname in self._FIELD_ORDER:
                wid = wd.get(fname)
                if wid is None:
                    continue
                fmt = self._get_cell_fmt(gi, fname)
                # Rebuild stylesheet: formatting + selection border
                parts = []
                parts.append(f"font-size: {fmt['font_size']}px;")
                if fmt.get("font_family"):
                    parts.append(f"font-family: '{fmt['font_family']}';")
                if fmt["bold"]:
                    parts.append("font-weight: bold;")
                if fmt["underline"]:
                    parts.append("text-decoration: underline;")
                if fmt["text_color"]:
                    parts.append(f"color: {fmt['text_color']};")
                if fmt["bg_color"]:
                    parts.append(f"background: {fmt['bg_color']};")
                if (gi, fname) in self._selected_cells:
                    parts.append(f"border: {self._SELECTION_BORDER}; border-radius: 4px;")
                else:
                    parts.append("border: none;")
                wid.setStyleSheet(" ".join(parts))

    def _get_selected_or_active(self):
        """Return the set of (gi, field) tuples — selected cells or just the active cell."""
        if self._selected_cells:
            return self._selected_cells
        # Fallback: single active cell
        gi = self._active_gi
        if gi >= 0 and gi < len(self._items):
            # Determine which field has focus
            wd = self._row_widgets.get(gi, {})
            for fname in self._FIELD_ORDER:
                wid = wd.get(fname)
                if wid and wid.hasFocus():
                    return {(gi, fname)}
        return set()

    def _apply_to_selected(self, prop, value=None):
        """Apply a formatting property to all selected cells (or active cell).

        For boolean props (bold/underline) value=None means toggle.
        For font_size, pass value as the new size.
        For font_family, pass the family name string.
        For text_color/bg_color, pass value as the color string.
        """
        targets = self._get_selected_or_active()
        if not targets:
            return
        for gi, fname in targets:
            wd = self._row_widgets.get(gi)
            if not wd:
                continue
            widget = wd.get(fname)
            if not widget:
                continue
            fmt = self._get_cell_fmt(gi, fname)
            if prop in ("bold", "underline"):
                fmt[prop] = not fmt[prop] if value is None else bool(value)
            elif prop == "font_size":
                fmt["font_size"] = max(8, min(24, value))
            elif prop == "font_family":
                fmt["font_family"] = value or ""
            elif prop in ("text_color", "bg_color"):
                fmt[prop] = value or ""
            elif prop == "reset":
                self._cell_formatting.pop((gi, fname), None)
            self._apply_cell_fmt(widget, gi, fname)
        self._highlight_selected_cells()

    # ===================== PART D+E: Event filter — DnD + keyboard shortcuts
    _FIELD_ORDER = ("desc", "size", "qty", "rate", "amt")

    def eventFilter(self, obj, ev):
        # --- PART E: Keyboard shortcuts for cell widgets ---
        if ev.type() == QEvent.FocusIn:
            for gi, wd in self._row_widgets.items():
                if obj in (wd["desc"], wd["size"], wd["qty"], wd["rate"], wd["amt"]):
                    self._active_gi = gi
                    break

        elif ev.type() == QEvent.KeyPress:
            key = ev.key()
            mods = ev.modifiers()

            # Enter → smart field navigation
            # Rate → Amount (same row), Amount → new row, others → next row
            if key in (Qt.Key_Return, Qt.Key_Enter):
                for gi, wd in self._row_widgets.items():
                    if obj in (wd["desc"], wd["size"], wd["qty"], wd["rate"], wd["amt"]):
                        self._active_gi = gi
                        # Rate field → jump to Amount field of same row
                        if obj is wd["rate"]:
                            wd["amt"].setFocus()
                            wd["amt"].selectAll()
                            return True
                        # Amount field → always add new row in same area
                        if obj is wd["amt"]:
                            self._add_item_to_area(self._items[gi].get("area") or "OTHER")
                            return True
                        # Other fields (desc, size, qty) → move to next row
                        nxt = gi + 1
                        if nxt < len(self._items):
                            nw = self._row_widgets.get(nxt)
                            if nw:
                                nw["desc"].setFocus()
                                self._active_gi = nxt
                                return True
                        else:
                            # at the last row → create a new row in the same area
                            self._add_item_to_area(self._items[gi].get("area") or "OTHER")
                            return True
                        break

            # Tab → move to next field in the same row, or first field of next row
            elif key == Qt.Key_Tab and not mods & Qt.ControlModifier:
                for gi, wd in self._row_widgets.items():
                    if obj in (wd["desc"], wd["size"], wd["qty"], wd["rate"], wd["amt"]):
                        # Find current field index
                        cur_idx = -1
                        for fi, fname in enumerate(self._FIELD_ORDER):
                            if obj is wd[fname]:
                                cur_idx = fi
                                break
                        nxt_field = cur_idx + 1
                        if nxt_field < len(self._FIELD_ORDER):
                            # Move to next field in same row
                            nxt_wid = wd[self._FIELD_ORDER[nxt_field]]
                            nxt_wid.setFocus()
                            nxt_wid.selectAll()
                        else:
                            # Move to first field of next row (or create new)
                            nxt_gi = gi + 1
                            if nxt_gi < len(self._items):
                                nw = self._row_widgets.get(nxt_gi)
                                if nw:
                                    nw["desc"].setFocus()
                                    self._active_gi = nxt_gi
                            else:
                                self._add_item_to_area(self._items[gi].get("area") or "OTHER")
                        return True

            # Shift+Tab → move to previous field in the same row
            elif key == Qt.Key_Backtab:
                for gi, wd in self._row_widgets.items():
                    if obj in (wd["desc"], wd["size"], wd["qty"], wd["rate"], wd["amt"]):
                        cur_idx = -1
                        for fi, fname in enumerate(self._FIELD_ORDER):
                            if obj is wd[fname]:
                                cur_idx = fi
                                break
                        prev_field = cur_idx - 1
                        if prev_field >= 0:
                            prev_wid = wd[self._FIELD_ORDER[prev_field]]
                            prev_wid.setFocus()
                            prev_wid.selectAll()
                        else:
                            # Move to last field of previous row
                            prev_gi = gi - 1
                            if prev_gi >= 0:
                                pw = self._row_widgets.get(prev_gi)
                                if pw:
                                    pw["amt"].setFocus()
                                    pw["amt"].selectAll()
                                    self._active_gi = prev_gi
                        return True

            # Delete → delete active row when focused in a cell
            # But NOT when the user is editing text (has selection or cursor
            # is not at the start of a non-empty field) — let QLineEdit handle it.
            elif key == Qt.Key_Delete and not mods:
                for gi, wd in self._row_widgets.items():
                    if obj in (wd["desc"], wd["size"], wd["qty"], wd["rate"], wd["amt"]):
                        # If text is selected, let the line edit handle the delete normally
                        if obj.hasSelectedText():
                            return False
                        # If field is non-empty and cursor is not at position 0, let the line edit delete
                        if obj.text() and obj.cursorPosition() > 0:
                            return False
                        self._active_gi = gi
                        self._delete_row(gi)
                        return True

            # Ctrl+D → duplicate row
            elif key == Qt.Key_D and mods & Qt.ControlModifier:
                self._duplicate_row()
                return True

            # Ctrl+B → toggle bold on selected cells (or current cell)
            elif key == Qt.Key_B and mods & Qt.ControlModifier:
                targets = self._get_selected_or_active()
                if targets:
                    self._apply_to_selected("bold")
                    return True

            # Ctrl+U → toggle underline on selected cells (or current cell)
            elif key == Qt.Key_U and mods & Qt.ControlModifier:
                targets = self._get_selected_or_active()
                if targets:
                    self._apply_to_selected("underline")
                    return True

            # Ctrl+C → copy current row to clipboard
            elif key == Qt.Key_C and mods & Qt.ControlModifier:
                for gi, wd in self._row_widgets.items():
                    if obj in (wd["desc"], wd["size"], wd["qty"], wd["rate"], wd["amt"]):
                        self._clipboard = dict(self._items[gi])
                        show_toast(self, "Row copied.", "info")
                        return True

            # Ctrl+V → paste row from clipboard
            elif key == Qt.Key_V and mods & Qt.ControlModifier:
                if self._clipboard:
                    for gi, wd in self._row_widgets.items():
                        if obj in (wd["desc"], wd["size"], wd["qty"], wd["rate"], wd["amt"]):
                            self._push_undo("paste row")
                            new_row = dict(self._clipboard)
                            self._items.insert(gi + 1, new_row)
                            self._rebuild_sections()
                            self._active_gi = gi + 1
                            self._mark_dirty()
                            show_toast(self, "Row pasted.", "info")
                            return True

            # Ctrl+S → save
            elif key == Qt.Key_S and mods & Qt.ControlModifier:
                self._save("SAVED")
                return True

            # Ctrl+Up / Ctrl+Down → move row up / down
            elif key == Qt.Key_Up and mods & Qt.ControlModifier:
                self._move(-1)
                return True
            elif key == Qt.Key_Down and mods & Qt.ControlModifier:
                self._move(1)
                return True

            # Ctrl+A → standard select-all text (do NOT hijack it for deletion)
            elif key == Qt.Key_A and mods & Qt.ControlModifier:
                return False

            # F1 → show keyboard shortcuts help
            elif key == Qt.Key_F1:
                self._show_shortcuts_help()
                return True

            # Escape → move focus out of the table
            elif key == Qt.Key_Escape:
                for gi, wd in self._row_widgets.items():
                    if obj in (wd["desc"], wd["size"], wd["qty"], wd["rate"], wd["amt"]):
                        # Move focus to the page title so the user is out of the table
                        self.title_label.setFocus()
                        return True

        # --- PART D: Drag-and-drop for table row reorder ---
        elif ev.type() == QEvent.MouseButtonPress and ev.button() == Qt.LeftButton:
            if hasattr(obj, '_drag_row'):  # It's our table
                idx = obj.indexAt(ev.pos())
                if idx.isValid():
                    obj._drag_row = idx.row()
                else:
                    obj._drag_row = -1

        # --- Ctrl+Click: multi-cell selection on cell widgets ---
        elif ev.type() == QEvent.MouseButtonPress and ev.button() == Qt.LeftButton and (ev.modifiers() & Qt.ControlModifier):
            for gi, wd in self._row_widgets.items():
                for fname in self._FIELD_ORDER:
                    if obj is wd[fname]:
                        self._toggle_cell_selection(gi, fname)
                        return True

        # --- Shift+Click: range selection on cell widgets ---
        elif ev.type() == QEvent.MouseButtonPress and ev.button() == Qt.LeftButton and (ev.modifiers() & Qt.ShiftModifier):
            for gi, wd in self._row_widgets.items():
                for fname in self._FIELD_ORDER:
                    if obj is wd[fname]:
                        if self._selected_cells:
                            # Extend from last selected cell
                            last_gi, last_field = max(self._selected_cells)
                            self._select_range(last_gi, last_field, gi, fname)
                        else:
                            self._toggle_cell_selection(gi, fname)
                        return True

        elif ev.type() == QEvent.DragEnter:
            if hasattr(obj, '_drag_row') and ev.mimeData().hasText():
                ev.acceptProposedAction()
                return True

        elif ev.type() == QEvent.Drop:
            if hasattr(obj, '_drag_row') and ev.mimeData().hasText():
                try:
                    source_row = int(ev.mimeData().text())
                except (ValueError, TypeError):
                    return False
                target_idx = obj.indexAt(ev.pos())
                if not target_idx.isValid():
                    return False
                target_row = target_idx.row()

                if source_row == target_row or source_row < 0:
                    return False

                # Find the global indices for source and target
                source_gi = self._gi_from_table_row(obj, source_row)
                target_gi = self._gi_from_table_row(obj, target_row)
                if source_gi is None or target_gi is None:
                    return False

                # Move the item
                item = self._items.pop(source_gi)
                # Adjust target if source was before target
                if source_gi < target_gi:
                    target_gi -= 1
                self._items.insert(target_gi, item)
                self._rebuild_sections()
                self._active_gi = target_gi
                return True

        # --- Right-click context menu on tables ---
        elif ev.type() == QEvent.ContextMenu and hasattr(obj, '_drag_row'):
                idx = obj.indexAt(ev.pos())
                if idx.isValid():
                    gi = self._gi_from_table_row(obj, idx.row())
                    if gi is not None and 0 <= gi < len(self._items):
                        self._active_gi = gi
                        self._show_row_context_menu(obj, ev.globalPos(), gi)
                        return True

        return super().eventFilter(obj, ev)

    def _show_row_context_menu(self, table, global_pos, gi):
        """Show a right-click context menu for a row."""
        menu = QMenu(self)
        menu.setStyleSheet(self._menu_qss())
        area = self._items[gi].get("area", "OTHER")

        # --- Font formatting submenu (applies to selected cells or all in this row) ---
        fmt_menu = menu.addMenu("\U0001F524  Format")
        n_sel = len(self._selected_cells)
        if n_sel > 0:
            fmt_menu.setTitle(f"\U0001F524  Format  ({n_sel} cells)")
        else:
            fmt_menu.setTitle("\U0001F524  Format Row")

        act_bold = fmt_menu.addAction("B  Bold  (Ctrl+B)")
        f_bold = QFont(); f_bold.setBold(True); act_bold.setFont(f_bold)
        act_bold.triggered.connect(lambda: self._apply_to_selected("bold"))

        act_ul = fmt_menu.addAction("U  Underline  (Ctrl+U)")
        f_ul = QFont(); f_ul.setUnderline(True); act_ul.setFont(f_ul)
        act_ul.triggered.connect(lambda: self._apply_to_selected("underline"))

        fmt_menu.addSeparator()

        # --- Font Family (bulk) ---
        fam_menu = fmt_menu.addMenu("\U0001F4DD  Font Family")
        for label, family in self._FONT_FAMILIES:
            act_fam = fam_menu.addAction(label)
            act_fam.triggered.connect(lambda _, f=family: self._apply_to_selected("font_family", f))
        fam_menu.addSeparator()
        act_fam_reset = fam_menu.addAction("\u21BA  Reset Font Family")
        act_fam_reset.triggered.connect(lambda: self._apply_to_selected("font_family", ""))

        fmt_menu.addSeparator()

        act_inc = fmt_menu.addAction("\U0001F50D+  Increase Font Size")
        act_inc.triggered.connect(self._increase_selected_font_size)
        act_dec = fmt_menu.addAction("\U0001F50D\u2212  Decrease Font Size")
        act_dec.triggered.connect(self._decrease_selected_font_size)
        act_reset_size = fmt_menu.addAction("\u21BA  Reset Font Size")
        act_reset_size.triggered.connect(lambda: self._apply_to_selected("font_size", self._DEFAULT_FONT_SIZE))

        fmt_menu.addSeparator()

        act_tc = fmt_menu.addAction("\U0001F3A8  Text Color...")
        act_tc.triggered.connect(self._pick_color_for_selected)
        act_tc_reset = fmt_menu.addAction("\u21BA  Reset Text Color")
        act_tc_reset.triggered.connect(lambda: self._apply_to_selected("text_color", ""))

        fmt_menu.addSeparator()

        act_bg = fmt_menu.addAction("\U0001F58C\uFE0F  Background Color...")
        act_bg.triggered.connect(self._pick_bg_for_selected)
        act_bg_reset = fmt_menu.addAction("\u21BA  Reset Background")
        act_bg_reset.triggered.connect(lambda: self._apply_to_selected("bg_color", ""))

        fmt_menu.addSeparator()

        act_reset = fmt_menu.addAction("\u2715  Reset All Formatting")
        act_reset.triggered.connect(lambda: self._apply_to_selected("reset"))

        act_clear_sel = fmt_menu.addAction("\u21BA  Clear Selection")
        act_clear_sel.triggered.connect(self._clear_selection)
        act_clear_sel.setEnabled(n_sel > 0)

        menu.addSeparator()

        act_copy = menu.addAction("\u2398  Copy Row  (Ctrl+C)")
        act_copy.triggered.connect(lambda: self._copy_row(gi))
        act_paste = menu.addAction("\u2399  Paste Row  (Ctrl+V)")
        act_paste.triggered.connect(lambda: self._paste_row_after(gi))
        act_paste.setEnabled(self._clipboard is not None)

        menu.addSeparator()

        act_dup = menu.addAction(f"{SYS_EDIT}  Duplicate Row")
        act_dup.triggered.connect(lambda: self._duplicate_row())

        menu.addSeparator()

        act_up = menu.addAction("\u25B2  Move Up")
        act_up.triggered.connect(lambda: self._move(-1))
        act_down = menu.addAction("\u25BC  Move Down")
        act_down.triggered.connect(lambda: self._move(1))

        menu.addSeparator()

        # Move to another area submenu
        areas = [a.name for a in catalog_service.list_areas() if a.name != "+"]
        other_areas = [a for a in areas if a != area]
        if other_areas:
            move_menu = menu.addMenu("\u2192  Move to Area")
            for target_area in other_areas:
                act = move_menu.addAction(target_area)
                act.triggered.connect(lambda _, t=target_area: self._move_to_area(gi, t))

        menu.addSeparator()

        act_del = menu.addAction(f"{SYS_DELETE}  Delete Row")
        act_del.triggered.connect(lambda: self._delete_row(gi))

        menu.exec(global_pos)

    def _increase_selected_font_size(self):
        targets = self._get_selected_or_active()
        for gi, fname in targets:
            fmt = self._get_cell_fmt(gi, fname)
            self._apply_to_selected("font_size", max(8, min(24, fmt["font_size"] + 1)))
            break  # all get the same delta

    def _decrease_selected_font_size(self):
        targets = self._get_selected_or_active()
        for gi, fname in targets:
            fmt = self._get_cell_fmt(gi, fname)
            self._apply_to_selected("font_size", max(8, min(24, fmt["font_size"] - 1)))
            break

    def _pick_color_for_selected(self):
        targets = self._get_selected_or_active()
        if not targets:
            return
        gi, fname = next(iter(targets))
        fmt = self._get_cell_fmt(gi, fname)
        current = QColor(fmt["text_color"]) if fmt["text_color"] else QColor(Qt.white)
        color = QColorDialog.getColor(current, self, "Choose Text Color")
        if color.isValid():
            self._apply_to_selected("text_color", color.name())

    def _pick_bg_for_selected(self):
        targets = self._get_selected_or_active()
        if not targets:
            return
        gi, fname = next(iter(targets))
        fmt = self._get_cell_fmt(gi, fname)
        current = QColor(fmt["bg_color"]) if fmt["bg_color"] else QColor(Qt.white)
        color = QColorDialog.getColor(current, self, "Choose Background Color")
        if color.isValid():
            self._apply_to_selected("bg_color", color.name())

    def _move_to_area(self, gi, target_area):
        """Move a row from its current area to another area."""
        if gi < 0 or gi >= len(self._items):
            return
        self._push_undo(f"move to {target_area}")
        self._items[gi]["area"] = target_area
        self._rebuild_sections()
        self._active_gi = gi
        self._mark_dirty()
        show_toast(self, f"Row moved to {target_area}", "success")

    def _copy_row(self, gi):
        """Copy a row's data to the internal clipboard."""
        if 0 <= gi < len(self._items):
            self._clipboard = dict(self._items[gi])
            show_toast(self, "Row copied.", "info")

    def _paste_row_after(self, gi):
        """Paste the clipboard row after index gi."""
        if not self._clipboard:
            show_toast(self, "Nothing to paste.", "info")
            return
        self._push_undo("paste row")
        new_row = dict(self._clipboard)
        self._items.insert(gi + 1, new_row)
        self._rebuild_sections()
        self._active_gi = gi + 1
        self._mark_dirty()
        show_toast(self, "Row pasted.", "info")

    def _gi_from_table_row(self, table, row):
        """Map a visible table row back to the global item index.

        Each section stores ``_start_gi`` (the global index of its first item)
        so the mapping is a simple offset calculation.
        """
        for sec in self._sections:
            if sec._table is table:
                start = getattr(sec, '_start_gi', None)
                if start is None:
                    # Fallback: find the first row widget belonging to this table
                    for gi, wd in self._row_widgets.items():
                        if wd["table"] is table:
                            start = gi - row
                            break
                if start is not None:
                    result = start + row
                    if 0 <= result < len(self._items):
                        return result
        return None

    def _renumber_all(self):
        for sw in self._sections:
            table = sw._table
            table.blockSignals(True)
            for r in range(table.rowCount()):
                it = table.item(r, 0)
                if it:
                    it.setText(str(r + 1))
            table.blockSignals(False)

    def _update_area_totals(self, area_totals):
        for sw in self._sections:
            area = sw._heading.text().strip("\u2014 ")
            amt = area_totals.get(area, 0.0)
            sw._total_label.setText(f"\u20B9 {amt:,.2f}")

    # ============================================================ row ops
    def _add_item_to_area(self, area):
        # Insert a new empty row into the given area (last position of that area)
        if not area:
            # first item: use the first real area
            areas = [a for a in catalog_service.list_areas() if a.name != "+"]
            area = areas[0].name if areas else "OTHER"
        self._push_undo(f"add row to {area}")
        row_d = {"area": area, "description": "", "size": "",
                 "qty_raw": "", "rate_raw": "", "amount": None}
        insert_at = len(self._items)
        for gi in range(len(self._items) - 1, -1, -1):
            if self._items[gi].get("area") == area:
                insert_at = gi + 1
                break
        self._items.insert(insert_at, row_d)
        self._rebuild_from_index(insert_at)
        self._recalc()
        self._active_gi = insert_at
        self._mark_dirty()
        w = self._row_widgets.get(insert_at)
        if w:
            w["desc"].setFocus()
            # Auto-show suggestion dropdown for the area's items
            completer = w["desc"].completer()
            if completer:
                # Refresh the completer model then trigger the popup
                if hasattr(w["desc"], "_refresh_completer"):
                    w["desc"]._refresh_completer()
                completer.setCompletionPrefix("")
                w["desc"].setText("")
                completer.complete()

    def _add_new_area(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Add New Area", "Area name (e.g. BALCONY):")
        if ok and name.strip():
            try:
                area = catalog_service.add_area(name.strip())
                self.add_menu.clear()
                self._populate_add_menu()
                self._add_item_to_area(area.name)
                show_toast(self, f"Area '{area.name}' added.", "success")
            except Exception as e:  # noqa: BLE001
                show_toast(self, f"Could not add area: {e}", "error")

    def _active_row_data(self):
        gi = self._active_gi
        if gi < 0 or gi >= len(self._items):
            gi = len(self._items) - 1 if self._items else -1
        return gi

    def _duplicate_row(self):
        gi = self._active_row_data()
        if gi < 0:
            return
        self._push_undo("duplicate row")
        src = dict(self._items[gi])
        self._items.insert(gi + 1, src)
        self._rebuild_from_index(gi + 1)
        self._recalc()
        self._active_gi = gi + 1
        self._mark_dirty()

    def _move(self, delta):
        gi = self._active_row_data()
        if gi < 0:
            return
        new = gi + delta
        if new < 0 or new >= len(self._items):
            return
        self._push_undo(f"move row {'up' if delta < 0 else 'down'}")
        self._items[gi], self._items[new] = self._items[new], self._items[gi]
        self._rebuild_sections()
        self._active_gi = new
        self._mark_dirty()

    def _delete_row(self, gi=None):
        r = gi if gi is not None else self._active_row_data()
        if r < 0 or r >= len(self._items):
            return
        if QMessageBox.question(
                self, "Delete Item", "Delete this item row?",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        desc = self._items[r].get("description", "") or f"row {r+1}"
        del_area = self._items[r].get("area", "OTHER") if r < len(self._items) else None
        self._push_undo(f"delete '{desc}'")
        self._items.pop(r)
        self._rebuild_from_index(r, area=del_area)
        self._recalc()
        self._mark_dirty()

    def _edit_row(self, gi):
        w = self._row_widgets.get(gi)
        if w:
            w["desc"].setFocus()

    def _measure_current(self):
        gi = self._active_row_data()
        if gi < 0:
            show_toast(self, "Select or focus a row first.", "info")
            return
        self._measure_row(gi)

    def _measure_row(self, gi):
        if gi < 0 or gi >= len(self._items):
            return
        helper = MeasurementHelper(self, current=self._items[gi].get("size", ""))
        if helper.exec():
            size = helper.result()
            if size:
                self._items[gi]["size"] = size
                w = self._row_widgets.get(gi)
                if w:
                    w["size"].setText(size)

    # ============================================================ cell handlers
    def _on_desc_changed(self, gi, text):
        if gi < len(self._items):
            self._items[gi]["description"] = text
            self._mark_dirty()

    def _on_size_changed(self, gi, text):
        if gi < len(self._items):
            self._items[gi]["size"] = text
            self._mark_dirty()

    def _on_qty_changed(self, gi, text):
        if gi < len(self._items):
            self._items[gi]["qty_raw"] = text
            self._recalc_soon()
            self._mark_dirty()

    def _on_rate_changed(self, gi, text):
        if gi < len(self._items):
            self._items[gi]["rate_raw"] = text
            self._recalc_soon()
            self._mark_dirty()

    def _on_amount_changed(self, gi, text):
        if gi < len(self._items):
            self._items[gi]["amount"] = text
            self._recalc_soon()
            self._mark_dirty()

    def _on_gst_toggled(self, checked):
        self.f_gst.setEnabled(bool(checked))
        self._recalc()

    def _apply_discount_pct(self, pct):
        """Apply a percentage discount based on current subtotal."""
        _computed, subtotal = calc.compute_rows(self._items)
        disc = round(subtotal * pct / 100.0, 2)
        self.f_discount.setValue(disc)
        self._mark_dirty()
        show_toast(self, f"{pct}% discount applied (\u20B9 {disc:,.2f})", "info")

    # ============================================================ calc
    def _recalc_soon(self):
        """Debounced recalculation used while typing in qty/rate/amount.

        Full invoice recalculation on every keystroke causes input lag with
        many items. This (re)starts a short single-shot timer so the totals,
        area totals, quick stats and progress bars update shortly after the
        user pauses typing.
        """
        self._skip_progress = True  # skip progress update during typing
        self._recalc_timer.start()

    def _recalc(self):
        computed, subtotal = calc.compute_rows(self._items)
        disc = min(self.f_discount.value(), subtotal)
        gst_rate = self.f_gst.value() if self.cb_gst.isChecked() else 0
        totals = calc.apply_gst(subtotal, disc, gst_rate)
        area_totals = calc.compute_area_totals(self._items)
        taxable = subtotal - disc

        for i, amt in enumerate(computed):
            w = self._row_widgets.get(i)
            if not w:
                continue
            q = self._items[i].get("qty_raw", "")
            rt = self._items[i].get("rate_raw", "")
            qn = calc.is_number(q)
            rn = calc.is_number(rt)
            manual = (not qn) and (not rn)  # LS/LS → user types the amount by hand
            try:
                w["amt"].setReadOnly(not manual)
            except Exception:  # noqa: BLE001
                manual = True
            if amt is not None and not manual:
                new = _fmt(amt)
                if w["amt"].text() != new:
                    w["amt"].blockSignals(True)
                    w["amt"].setText(new)
                    w["amt"].blockSignals(False)

        self._sum_row_set(self.l_subtotal, _money(totals["subtotal"]))
        self._sum_row_set(self.l_discount, "-\u20B9 {:,.2f}".format(totals["discount"]))
        self._sum_row_set(self.l_taxable, _money(taxable))
        gst_frame = getattr(self.l_gst, "_stat_frame", None) or self.l_gst
        if self.cb_gst.isChecked():
            self._sum_row_set(self.l_gst, _money(totals["gst_amount"]))
            self.l_gst.setVisible(True)
            gst_frame.setVisible(True)
        else:
            self._sum_row_set(self.l_gst, "\u20B9 0.00")
            self.l_gst.setVisible(False)
            gst_frame.setVisible(False)

        self.l_grand.setText(_money(totals["grand_total"]))
        self.l_words.setText(calc.amount_in_words(totals["grand_total"]))

        # Update Advance / Paid and Balance Due
        inv_id = self.get_invoice_id()
        if inv_id and hasattr(self, 'l_paid'):
            try:
                from app.services import payment_service
                s = payment_service.invoice_payment_summary(inv_id)
                paid_amt = float(s["paid"] or 0)
                bal_amt = max(float(totals["grand_total"]) - paid_amt, 0.0)
                self.l_paid.setText(f"\u20B9 {paid_amt:,.2f}")
                if bal_amt == 0 and paid_amt > 0:
                    self.l_balance.setText("\u2705 Fully Settled")
                    self.l_balance.setStyleSheet("font-size: 14px; font-weight: 800; color: #059669;")
                else:
                    self.l_balance.setText(f"\u20B9 {bal_amt:,.2f}")
                    self.l_balance.setStyleSheet("font-size: 15px; font-weight: 800; color: #DC2626;")
            except Exception:  # noqa: BLE001
                pass
        elif hasattr(self, 'l_paid'):
            self.l_paid.setText("\u20B9 0.00")
            self.l_balance.setText(_money(totals["grand_total"]))
            self.l_balance.setStyleSheet("font-size: 15px; font-weight: 800; color: #DC2626;")

        self._update_area_totals(area_totals)
        # Update quick stats bar
        self._update_quick_stats(computed, totals)
        # Update progress indicator only when not triggered by typing debounce
        if not getattr(self, '_skip_progress', False):
            self._update_progress()
        self._skip_progress = False

    # ============================================================ save
    def _save(self, status):
        # Commit any pending debounced recalculation so totals are up to date.
        if self._recalc_timer.isActive():
            self._recalc_timer.stop()
            self._recalc()

        cid = self.f_customer.currentData()
        if not cid:
            QMessageBox.warning(self, "Customer required",
                                "Please select a customer before saving.")
            return
        items = []
        for it in self._items:
            q = it.get("qty_raw", "")
            rt = it.get("rate_raw", "")
            amt = None
            if calc.is_number(q) and calc.is_number(rt):
                amt = calc.row_amount(q, rt)
            else:
                amt = it.get("amount")
                if amt == "" or amt is None or not calc.is_number(amt):
                    amt = None
            items.append({
                "area": it.get("area", ""),
                "description": it.get("description", ""),
                "size": it.get("size", ""),
                "qty_raw": q,
                "rate_raw": rt,
                "amount": float(amt) if calc.is_number(amt) else None,
            })
        if status != "DRAFT" and not items:
            QMessageBox.warning(self, "No items",
                                "Please add at least one item before saving.")
            return

        # Warn about LS items that have no manual AMOUNT (they would silently
        # save as 0). Only enforced on final saves, not while drafting.
        if status != "DRAFT":
            ls_missing = [
                (i + 1, it.get("description") or "(no description)")
                for i, it in enumerate(items)
                if (not calc.is_number(it.get("qty_raw", ""))
                    and not calc.is_number(it.get("rate_raw", ""))
                    and it.get("amount") is None)
            ]
            if ls_missing:
                shown = "; ".join(f"#{n} {d}" for n, d in ls_missing[:8])
                if len(ls_missing) > 8:
                    shown += f" (+{len(ls_missing) - 8} more)"
                reply = QMessageBox.warning(
                    self, "LS items missing amount",
                    f"{len(ls_missing)} item(s) have LS in QTY/RATE but no "
                    f"manual AMOUNT. So save par inke liye amount 0 (zero) "
                    f"hoga.\n\n{shown}\n\nPhir bhi save karein?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply != QMessageBox.Yes:
                    return

        subtotal_now = calc.compute_rows([{"qty_raw": it.get("qty_raw"), "rate_raw": it.get("rate_raw"), "amount": it.get("amount")} for it in items])[1]
        data = {
            "customer_id": cid,
            "project_id": None,
            "invoice_date": self.f_date.date().toPython(),
            "due_date": self.f_due.date().toPython(),
            "site_address": self.f_site_addr.text().strip(),
            "discount": min(self.f_discount.value(), subtotal_now),
            "gst_enabled": self.cb_gst.isChecked(),
            "gst_rate": self.f_gst.value() if self.cb_gst.isChecked() else 0,
            "status": status,
            "invoice_prefix": business_service.get_invoice_prefix(),
            "invoice_number": self.f_invoice_no.text().strip() or None,
            "notes": self.f_notes.text().strip(),
        }
        try:
            if self.invoice:
                inv = invoice_service.update_invoice(self.invoice.id, data, items)
                self.invoice = inv
                show_toast(self, f"Invoice {inv.invoice_number} updated.", "success")
            else:
                inv = invoice_service.create_invoice(data, items)
                self.invoice = inv
                self.title_label.setText(f"Edit Invoice #{inv.invoice_number}")
                self.crumb_label.setText("Invoices  ›  Edit Invoice")
                self.f_invoice_no.setText(inv.invoice_number)
                show_toast(self, f"Invoice {inv.invoice_number} saved.", "success")
            self._mark_clean()
            self._undo_stack.clear()
            # Show WhatsApp and Print buttons after successful save
            if self.invoice:
                self.btn_whatsapp.setVisible(True)
                self.btn_print_direct.setVisible(True)
            if self.on_close_callback:
                self.on_close_callback(refresh=True)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", str(e))

    def current_items(self):
        return list(self._items)

    def get_invoice_id(self):
        return self.invoice.id if self.invoice else None

    def _preview_pdf(self):
        """Save as draft first, then open PDF preview."""
        if self._dirty:
            cid = self.f_customer.currentData()
            if cid:
                try:
                    self._save("DRAFT")
                except Exception:  # noqa: BLE001, S110
                    pass
        inv_id = self.get_invoice_id()
        if not inv_id:
            show_toast(self, "Save the invoice first to preview PDF.", "info")
            return
        try:
            from app.pdf.pdf_service import PdfPreviewDialog
            dlg = PdfPreviewDialog(inv_id, self)
            dlg.exec()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Preview failed", str(e))

    def _close_editor(self):
        if self._dirty:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Save as draft before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                self._save("DRAFT")
            elif reply == QMessageBox.Cancel:
                return
        if self.on_close_callback:
            self.on_close_callback()

    # helper usable by headless tests
    def set_active_row(self, gi):
        self._active_gi = gi


class QTextEditBox(QWidget):
    """Small multi-line editor placeholder used by the New Customer dialog."""
    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QTextEdit as TE
        self._te = TE(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._te)

    def toPlainText(self) -> str:
        return self._te.toPlainText()

    def setFixedHeight(self, h):
        pass  # height handled by layout


# ========================== PART F: Improved item picker ==========================
def make_suggestion_lineedit(base: QLineEdit, gi: int, area: str,
                             editor: InvoiceEditor) -> QLineEdit:
    """Searchable + custom-entry description with area-aware autocomplete.

    Shows matching items grouped by area, with an "＋ Add custom item" option
    when the typed text doesn't match any existing item. Free-typing is always
    allowed — the custom item option is just a convenience hint.
    """
    from PySide6.QtCore import QStringListModel
    from PySide6.QtWidgets import QCompleter

    completer = QCompleter(base)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    completer.setFilterMode(Qt.MatchContains)
    base.setCompleter(completer)

    def refresh():
        text = base.text().strip()
        items = catalog_service.suggest_items(area, text, limit=50)
        names = [i.name for i in items]

        # Show "＋ Add custom item" option when text is non-empty and doesn't
        # match an existing item exactly — makes it obvious free-typing is ok.
        if text and text not in names:
            names.append(f"＋ Add custom item: \"{text}\"")

        completer.setModel(QStringListModel(names, completer))

    base._refresh_completer = refresh
    base.textChanged.connect(refresh)

    focus_filter = _FocusRefresh(base, refresh)
    base.installEventFilter(focus_filter)
    base._focus_filter = focus_filter
    return base


class _FocusRefresh(QObject):
    def __init__(self, target, refresh):
        super().__init__(target)
        self.target = target
        self.refresh = refresh

    def eventFilter(self, obj, ev):
        if obj is self.target and ev.type() == QEvent.FocusIn:
            self.refresh()
        return super().eventFilter(obj, ev)

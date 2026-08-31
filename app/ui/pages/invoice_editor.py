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

from PySide6.QtCore import QMimeData, QObject, QPoint, QEvent, Qt, QDate
from PySide6.QtGui import QKeySequence, QShortcut, QDrag
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
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
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services import business_service, catalog_service, customer_service, invoice_service
from app.services.invoice_service import next_invoice_number
from app.ui.widgets.common import show_toast
from app.utils import calculations as calc


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
        return ("%g" % f)
    return str(v)


def _money(v) -> str:
    try:
        return f"\u20B9 {float(v or 0):,.2f}"
    except (TypeError, ValueError):
        return f"\u20B9 0.00"


class MeasurementHelper(QDialog):
    """Feet/inches helper that builds a Size text like 6'6\" x 6'."""

    def __init__(self, parent=None, current=""):
        super().__init__(parent)
        self.setWindowTitle("Measurement Helper")
        self.setMinimumWidth(400)
        v = QVBoxLayout(self)
        v.setSpacing(14)

        title = QLabel("Enter length and width in feet / inches")
        title.setObjectName("dialogTitle")
        v.addWidget(title)

        hint = QLabel("Example: 9' 6\" length   x   6' width   →   9'6\" × 6'")
        hint.setStyleSheet("color:#6B7280;")
        v.addWidget(hint)

        def spin(maxv=300):
            s = QSpinBox()
            s.setRange(0, maxv)
            s.setValue(0)
            s.setAlignment(Qt.AlignCenter)
            return s

        self.f1 = spin(); self.i1 = spin(12)
        self.f2 = spin(); self.i2 = spin(12)

        form = QFormLayout()
        form.setVerticalSpacing(12)

        def ft_in_row(f, i, label):
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(f); row.addWidget(QLabel("ft"))
            row.addWidget(i); row.addWidget(QLabel("in"))
            row.addStretch(1)
            return label, row

        form.addRow(*ft_in_row(self.f1, self.i1, "Length:"))
        form.addRow(*ft_in_row(self.f2, self.i2, "Width:"))
        v.addLayout(form)

        self._parse_current(current)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Insert")
        ok.setObjectName("primaryButton")
        ok.clicked.connect(self._ok)
        btns.addWidget(cancel); btns.addWidget(ok)
        v.addLayout(btns)

    def _parse_current(self, current):
        if not current or not isinstance(current, str):
            return
        parts = [p.strip() for p in current.split("x") if p.strip()]
        if len(parts) != 2:
            return

        def to_vals(s):
            import re
            ft = re.search(r"(\d+)'", s)
            inch = re.search(r'(\d+)"', s)
            return (int(ft.group(1)) if ft else 0, int(inch.group(1)) if inch else 0)

        f1, i1 = to_vals(parts[0]); f2, i2 = to_vals(parts[1])
        self.f1.setValue(f1); self.i1.setValue(i1)
        self.f2.setValue(f2); self.i2.setValue(i2)

    def _ok(self):
        def part(ft, inch):
            if inch == 0:
                return f"{ft}'"
            return f"{ft}'{inch}\""
        self._size = f"{part(self.f1.value(), self.i1.value())} × {part(self.f2.value(), self.i2.value())}"
        self.accept()

    def result(self) -> str:
        return getattr(self, "_size", "")


class InvoiceEditor(QWidget):
    """Full invoice editing surface."""

    COLUMNS = ["S.N.", "DESCRIPTION / ITEM", "SIZE / MEASUREMENT", "QTY",
               "RATE (\u20B9)", "AMOUNT (\u20B9)", "ACTION"]

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
        self._build()
        self._setup_shortcuts()
        self._setup_autosave()
        self._load_invoice(invoice, customer_id)

    # ============================================================ UI build
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 10, 16, 12)
        root.setSpacing(8)

        root.addLayout(self._build_action_bar())

        # Top row: ultra-compact Invoice Details (left) + Summary (right top)
        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        top_row.addWidget(self._build_header_card(), 1)
        top_row.addWidget(self._build_summary_panel(), 0)
        root.addLayout(top_row, 0)  # stretch=0: top row is minimum height only

        # Items & Area Entry fills ALL remaining height — this is where data entry
        # happens, so it gets priority space.
        root.addWidget(self._build_items_card(), 1)

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

    # ---------------------------------------------------- undo / auto-save
    def _setup_autosave(self):
        """Auto-save as draft every 60 seconds if there are unsaved changes."""
        from PySide6.QtCore import QTimer
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(60_000)  # 60 seconds
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start()

    def _autosave(self):
        """Save as draft if there are unsaved changes and a customer is selected."""
        if not self._dirty:
            return
        cid = self.f_customer.currentData()
        if not cid:
            return  # Can't auto-save without a customer
        try:
            self._save("DRAFT")
            self._dirty = False
            show_toast(self, "Auto-saved draft.", "info")
        except Exception:  # noqa: BLE001
            pass  # Silently fail — don't interrupt the user

    def _mark_dirty(self):
        """Mark the invoice as having unsaved changes."""
        self._dirty = True

    def _mark_clean(self):
        """Mark the invoice as clean (saved)."""
        self._dirty = False

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
            "QTableWidget { background: white; alternate-background-color: #F6F8FC;"
            " border: 1px solid #E5E7EB; border-radius: 8px; }"
            "QHeaderView::section { background: #173560; color: white; font-weight: 600;"
            " padding: 6px; border: none; }"
        )
        for i, (key, action) in enumerate(shortcuts):
            key_item = QTableWidgetItem(key)
            key_item.setFont(key_item.font())
            from PySide6.QtGui import QFont
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
        bar.setSpacing(0)
        bar.setContentsMargins(0, 0, 0, 0)

        # top row: breadcrumb (left) + Back + Save buttons (right) — compact single line
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        crumb = QLabel("Invoices  ›  New Invoice")
        crumb.setStyleSheet("color:#6B7280; font-size:11px;")
        top.addWidget(crumb)
        top.addStretch(1)
        btn_draft = self._btn("Save Draft")
        btn_draft.setStyleSheet("font-size:11px; padding:4px 10px;")
        btn_draft.clicked.connect(lambda: self._save("DRAFT"))
        btn_save = self._btn("✓ Save", "primaryButton")
        btn_save.setStyleSheet("font-size:11px; padding:4px 10px;")
        btn_save.clicked.connect(lambda: self._save("SAVED"))
        self.back_btn = self._btn("← Back")
        self.back_btn.setObjectName("backButton")
        self.back_btn.setStyleSheet("font-size:11px; padding:4px 10px;")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self._close_editor)
        top.addWidget(btn_draft)
        top.addWidget(btn_save)
        top.addWidget(self.back_btn)
        bar.addLayout(top)

        self.title_label = QLabel("New Invoice")
        self.title_label.setObjectName("pageTitle")
        self.title_label.setStyleSheet("font-size:16px; font-weight:700; padding-top:2px;")

        bar.addWidget(self.title_label)

        # override crumb text on edit
        self.crumb_label = crumb
        return bar

    # ========================= PART A: Invoice Details — 4-row compact layout
    def _build_header_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("editorSection")
        card.setStyleSheet(
            "QFrame#editorSection { background: white; border: 1px solid #E5E7EB; border-radius: 10px; }"
            "QLabel#fieldLabel { color: #6B7280; font-size: 10px; font-weight: 600; }"
            "QLineEdit, QComboBox, QDateEdit { padding: 4px 8px; font-size: 12px; }"
        )
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(4)

        # Title — single compact line, buttons are in the action bar above
        title = self._section_title("\uD83D\uDCC4", "Invoice Details")
        title.setStyleSheet("color:#173560; font-size:11px; font-weight:700;")
        v.addWidget(title)

        # --- Ultra-compact grid: labels above inputs, minimal spacing ---
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(2)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        grid.setColumnStretch(5, 1)

        self.f_invoice_no = QLineEdit()
        self.f_invoice_no.setReadOnly(True)
        self.f_date = QDateEdit(QDate.currentDate())
        self.f_date.setCalendarPopup(True)
        self.f_due = QDateEdit(QDate.currentDate().addDays(7))
        self.f_due.setCalendarPopup(True)

        self.f_customer = QComboBox()
        self.f_customer.setEditable(True)
        self.f_customer.setInsertPolicy(QComboBox.NoInsert)
        self.f_customer.completer().setFilterMode(Qt.MatchContains)
        self.f_customer.completer().setCaseSensitivity(Qt.CaseInsensitive)
        self.f_customer.currentIndexChanged.connect(self._on_customer_changed)
        self.f_customer.lineEdit().setPlaceholderText("Search by name or mobile...")
        self.f_customer.lineEdit().textChanged.connect(self._on_customer_search)

        self.f_site = QLineEdit()
        self.f_site.setPlaceholderText("Project / Site name")
        self.f_site_addr = QLineEdit()
        self.f_site_addr.setPlaceholderText("Street, city, state, pincode")

        # Row 0: Invoice No | Date | Due Date + quick presets
        grid.addWidget(self._field_label("INVOICE NO."), 0, 0)
        grid.addWidget(self.f_invoice_no, 1, 0)
        grid.addWidget(self._field_label("DATE"), 0, 2)
        grid.addWidget(self.f_date, 1, 2)
        grid.addWidget(self._field_label("DUE DATE"), 0, 4)
        due_row = QHBoxLayout()
        due_row.setSpacing(3)
        due_row.addWidget(self.f_due, 1)
        for days, label in [(7, "7d"), (14, "14d"), (30, "30d")]:
            btn = self._btn(label)
            btn.setFixedSize(32, 22)
            btn.setStyleSheet("font-size:10px; padding:1px; border-radius:4px;")
            btn.clicked.connect(lambda _, d=days: self.f_due.setDate(
                QDate.currentDate().addDays(d)))
            due_row.addWidget(btn)
        grid.addLayout(due_row, 1, 4)

        # Row 1: Customer (+New) | Project/Site | Site Address
        cust_row = QHBoxLayout()
        cust_row.setSpacing(4)
        cust_row.addWidget(self.f_customer, 1)
        btn_new_cust = self._btn("+ New")
        btn_new_cust.clicked.connect(self._new_customer)
        cust_row.addWidget(btn_new_cust)
        grid.addWidget(self._field_label("CUSTOMER"), 2, 0)
        grid.addLayout(cust_row, 3, 0, 1, 2)
        grid.addWidget(self._field_label("PROJECT / SITE"), 2, 2)
        grid.addWidget(self.f_site, 3, 2)
        grid.addWidget(self._field_label("SITE ADDRESS"), 2, 4)
        grid.addWidget(self.f_site_addr, 3, 4)

        v.addLayout(grid)

        # Notes / Remarks row — ultra-compact
        notes_row = QHBoxLayout()
        notes_row.setSpacing(6)
        notes_lbl = QLabel("NOTES")
        notes_lbl.setObjectName("fieldLabel")
        notes_lbl.setStyleSheet("color:#6B7280; font-size:10px; font-weight:600;")
        self.f_notes = QLineEdit()
        self.f_notes.setPlaceholderText("Internal notes (not on PDF)")
        self.f_notes.setStyleSheet("font-size:11px; padding:2px 6px;")
        notes_row.addWidget(notes_lbl)
        notes_row.addWidget(self.f_notes, 1)
        v.addLayout(notes_row)

        return card

    def _btn(self, text, object_name=None) -> QPushButton:
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        if object_name:
            b.setObjectName(object_name)
        return b

    # ==================== PART B+C: Items & Area Entry — grouped toolbar
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
        v.addLayout(head)

        # --- PART C: Grouped toolbar with labels + separators ---
        tb = QHBoxLayout()
        tb.setSpacing(4)

        # Group: Add
        add_lbl = QLabel("Add:")
        add_lbl.setObjectName("toolbarGroupLabel")
        add_lbl.setStyleSheet("color:#6B7280; font-size:11px; font-weight:700; padding-left:4px;")
        tb.addWidget(add_lbl)
        btn_add_menu = self._btn("+ Add Item ▾", "primaryButton")
        self.add_menu = QMenu()
        btn_add_menu.setMenu(self.add_menu)
        self._populate_add_menu()
        tb.addWidget(btn_add_menu)
        btn_new_area = self._btn("+ New Area")
        btn_new_area.clicked.connect(self._add_new_area)
        tb.addWidget(btn_new_area)

        tb.addWidget(self._tb_sep())

        # Group: Row
        row_lbl = QLabel("Row:")
        row_lbl.setStyleSheet("color:#6B7280; font-size:11px; font-weight:700; padding-left:4px;")
        tb.addWidget(row_lbl)
        btn_dup = self._btn("\u2398 Duplicate")
        btn_dup.clicked.connect(self._duplicate_row)
        btn_up = self._btn("\u25B2 Up")
        btn_up.clicked.connect(lambda: self._move(-1))
        btn_down = self._btn("\u25BC Down")
        btn_down.clicked.connect(lambda: self._move(1))
        btn_del = self._btn("\u2715 Delete")
        btn_del.setObjectName("ghostButton")
        btn_del.clicked.connect(lambda: self._delete_row())
        tb.addWidget(btn_dup)
        tb.addWidget(btn_up)
        tb.addWidget(btn_down)
        tb.addWidget(btn_del)

        tb.addWidget(self._tb_sep())

        # Group: Tools
        tools_lbl = QLabel("Tools:")
        tools_lbl.setStyleSheet("color:#6B7280; font-size:11px; font-weight:700; padding-left:4px;")
        tb.addWidget(tools_lbl)
        btn_meas = self._btn("\uD83D\uDCD0 Measure")
        btn_meas.clicked.connect(self._measure_current)
        self.btn_meas = btn_meas
        tb.addWidget(btn_meas)
        btn_preview = self._btn("\uD83D\uDCC4 Preview PDF")
        btn_preview.clicked.connect(self._preview_pdf)
        tb.addWidget(btn_preview)

        tb.addStretch(1)

        # Item count indicator
        self.item_count_label = QLabel("0 items")
        self.item_count_label.setStyleSheet("color:#173560; font-size:11px; font-weight:600; padding-right:8px;")
        tb.addWidget(self.item_count_label)

        # Shortcut hints on the right
        hints = QLabel("Tab: fields  |  Ctrl+D: dup  |  Ctrl+C/V: copy/paste  |  Ctrl+↑↓: move  |  Ctrl+Z: undo  |  F1: all shortcuts")
        hints.setStyleSheet("color:#9CA3AF; font-size:11px; padding-right:2px;")
        tb.addWidget(hints)

        v.addLayout(tb)

        # Area sections container — fills remaining height, scrolls internally
        self.areas_scroll = QScrollArea()
        self.areas_scroll.setWidgetResizable(True)
        self.areas_scroll.setFrameShape(QFrame.NoFrame)
        self.areas_container = QWidget()
        self.areas_layout = QVBoxLayout(self.areas_container)
        self.areas_layout.setContentsMargins(0, 2, 4, 0)
        self.areas_layout.setSpacing(8)
        self.areas_scroll.setWidget(self.areas_container)
        v.addWidget(self.areas_scroll, 1)
        return card

    def _tb_sep(self) -> QFrame:
        s = QFrame()
        s.setFixedWidth(1)
        s.setFixedHeight(26)
        s.setStyleSheet("background:#D7DEE9;")
        return s

    def _items_hint(self) -> QLabel:
        l = QLabel('Pick an Area from "+ Add Item ▾" to start  ·  Qty or Rate = LS for manual amount')
        l.setStyleSheet("color:#6B7280; font-size:12px;")
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

    # ==================== PART B: Summary panel (unchanged structurally)
    def _build_summary_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("summaryPanel")
        panel.setMinimumWidth(330)
        panel.setMaximumWidth(430)
        v = QVBoxLayout(panel)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(5)

        title = QLabel("SUMMARY")
        title.setObjectName("summaryTitle")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        # GST + Discount on one compact line
        gd = QHBoxLayout()
        gd.setSpacing(10)
        self.cb_gst = QCheckBox("GST")
        self.cb_gst.setCursor(Qt.PointingHandCursor)
        self.cb_gst.setStyleSheet("color:white; font-weight:600;")
        self.cb_gst.toggled.connect(self._on_gst_toggled)
        gd.addWidget(self.cb_gst)

        rl = QLabel("Rate %")
        rl.setStyleSheet("color:#C9D6EA;")
        self.f_gst = QDoubleSpinBox()
        self.f_gst.setRange(0, 100)
        self.f_gst.setDecimals(2)
        self.f_gst.setSuffix(" %")
        self.f_gst.valueChanged.connect(self._recalc)
        gd.addWidget(rl)
        gd.addWidget(self.f_gst)

        dl = QLabel("Disc")
        dl.setStyleSheet("color:#C9D6EA;")
        self.f_discount = QDoubleSpinBox()
        self.f_discount.setRange(0, 1_000_000_000)
        self.f_discount.setDecimals(2)
        self.f_discount.setPrefix("\u20B9 ")
        self.f_discount.valueChanged.connect(self._recalc)
        gd.addWidget(dl)
        gd.addWidget(self.f_discount, 1)
        v.addLayout(gd)

        # Discount quick presets
        disc_presets = QHBoxLayout()
        disc_presets.setSpacing(3)
        disc_lbl = QLabel("Quick:")
        disc_lbl.setStyleSheet("color:#C9D6EA; font-size:10px;")
        disc_presets.addWidget(disc_lbl)
        for pct in [5, 10, 15, 20]:
            btn = self._btn(f"{pct}%")
            btn.setFixedSize(34, 20)
            btn.setStyleSheet("font-size:10px; padding:1px; border-radius:4px;")
            btn.clicked.connect(lambda _, p=pct: self._apply_discount_pct(p))
            disc_presets.addWidget(btn)
        disc_presets.addStretch(1)
        v.addLayout(disc_presets)

        v.addWidget(self._divider())

        # 2x2 grid of totals to save vertical height
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(3)
        self.l_subtotal = self._sum_row("Subtotal")
        self.l_discount = self._sum_row("Discount")
        self.l_taxable = self._sum_row("Taxable")
        self.l_gst = self._sum_row("GST")
        grid.addWidget(self.l_subtotal, 0, 0)
        grid.addWidget(self.l_discount, 0, 1)
        grid.addWidget(self.l_taxable, 1, 0)
        grid.addWidget(self.l_gst, 1, 1)
        v.addLayout(grid)

        v.addWidget(self._divider())

        gl = QLabel("GRAND TOTAL")
        gl.setObjectName("grandTotalLabel")
        gl.setAlignment(Qt.AlignCenter)
        self.l_grand = QLabel("\u20B9 0.00")
        self.l_grand.setObjectName("grandTotalValue")
        self.l_grand.setAlignment(Qt.AlignCenter)
        v.addWidget(gl)
        v.addWidget(self.l_grand)

        self.l_words = QLabel("Zero Rupees Only")
        self.l_words.setObjectName("wordsValue")
        self.l_words.setWordWrap(True)
        self.l_words.setAlignment(Qt.AlignCenter)
        v.addWidget(self.l_words)

        return panel

    def _divider(self) -> QFrame:
        d = QFrame()
        d.setObjectName("summaryDivider")
        d.setFixedHeight(1)
        return d

    def _sum_row(self, label) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 2, 0, 2)
        l = QLabel(label)
        l.setObjectName("summaryRowLabel")
        val = QLabel("\u20B9 0.00")
        val.setObjectName("summaryRowValue")
        val.setAlignment(Qt.AlignRight)
        lay.addWidget(l); lay.addStretch(1); lay.addWidget(val)
        setattr(w, "_value_label", val)
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
                self.f_customer.setCurrentIndex(idx if idx >= 0 else 0)
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
                self.f_customer.setCurrentIndex(idx if idx >= 0 else 0)
            self.f_site.setText(invoice.project.name if invoice.project else invoice.site_address or "")
            self.f_site_addr.setText(invoice.site_address or "")
            self.f_notes.setText(invoice.notes or "")
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
            profile = business_service.get_profile()
            self.cb_gst.setChecked(bool(profile and profile.show_gst))
            self.f_gst.setEnabled(bool(profile and profile.show_gst))
            self.f_gst.setValue(float(profile.default_gst_rate or 0)
                                if (profile and profile.show_gst) else 0)
            prefix = business_service.get_invoice_prefix()
            self.f_invoice_no.setText(next_invoice_number(prefix))
            if customer_id:
                idx = self.f_customer.findData(customer_id)
                self.f_customer.setCurrentIndex(idx if idx >= 0 else 0)
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
        self._sections = []
        self._row_widgets = {}

    def _rebuild_sections(self):
        self._clear_sections()
        for sec in self._group_sections():
            self._build_section(sec)
        # "+ Add New Area" footer button
        btn_new_area = self._btn("+ Add New Area")
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

    # ========================= PART B: Area section — merged header bar
    def _build_section(self, sec):
        area = sec["area"]
        sec_widget = QFrame()
        sec_widget.setObjectName("areaSection")
        v = QVBoxLayout(sec_widget)
        v.setContentsMargins(12, 12, 12, 14)
        v.setSpacing(10)

        count = sec["end"] - sec["start"]

        # --- Single-line header bar: ▾ Area Name | count | TOTAL + Add btn ---
        head = QHBoxLayout()
        head.setSpacing(6)

        # Collapse/expand toggle
        collapse_btn = self._btn("▾")
        collapse_btn.setFixedSize(24, 24)
        collapse_btn.setStyleSheet(
            "font-size:12px; padding:0; border:none; color:#173560; font-weight:700;"
            " background:transparent; border-radius:4px;"
        )
        collapse_btn.setCursor(Qt.PointingHandCursor)
        collapse_btn.setToolTip("Collapse / Expand area")
        head.addWidget(collapse_btn)

        heading = QLabel(area)
        heading.setObjectName("areaHeading")
        badge = QLabel(f"{count} item" + ("s" if count != 1 else ""))
        badge.setObjectName("areaCountBadge")
        head.addWidget(heading)
        head.addWidget(badge)
        head.addStretch(1)
        total_label = QLabel(f"{area} TOTAL  \u20B9 0.00")
        total_label.setObjectName("areaTotalHeading")
        head.addWidget(total_label)
        add_btn = self._btn("+ Add Item in " + area, "primaryButton")
        add_btn.clicked.connect(lambda _, a=area: self._add_item_to_area(a))
        head.addWidget(add_btn)
        v.addLayout(head)

        # --- PART B: Table with stronger grid, navy header, DnD support ---
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

        table.setStyleSheet(
            # Base table
            "QTableWidget { background: white; alternate-background-color: #F6F8FC;"
            " border: 1.5px solid #B8C6DB; border-radius: 10px;"
            " gridline-color: #C8D2E6; selection-background-color: transparent; }"
            # Cells
            "QTableWidget::item { padding: 4px 6px; border: none;"
            " border-bottom: 1px solid #DDE3EC; }"
            "QTableWidget::item:selected { background: #EFF3FA; color: #173560; }"
            "QTableWidget::item:hover { background: #EFF3FA; }"
            # Inputs inside cells — fill cell
            "QTableWidget QLineEdit { background: white; border: 1px solid #D7DEE9;"
            " border-radius: 5px; padding: 4px 6px; font-size: 13px;"
            " selection-background-color: #173560; }"
            "QTableWidget QLineEdit:focus { border-color: #C7A24B;"
            " background: #FFFDF5; }"
            # Drop indicator styling
            "QTableWidget QTableView DropIndicator { background: #C7A24B; }"
        )

        hh = table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(6, QHeaderView.Fixed)
        table.setColumnWidth(0, 44)
        table.setColumnWidth(2, 150)
        table.setColumnWidth(3, 90)
        table.setColumnWidth(4, 110)
        table.setColumnWidth(5, 130)
        table.setColumnWidth(6, 122)
        table.verticalHeader().setDefaultSectionSize(48)

        # populate rows for this section
        for gi in range(sec["start"], sec["end"]):
            self._insert_row(table, gi)

        # Install DnD event filter on the table
        table._drag_row = -1
        table.installEventFilter(self)

        v.addWidget(table, 1)

        self.areas_layout.addWidget(sec_widget)
        sec_widget._table = table
        sec_widget._total_label = total_label
        sec_widget._add_btn = add_btn
        sec_widget._heading = heading
        sec_widget._start_gi = sec["start"]  # global index of first item in this section
        sec_widget._collapsed = False

        # Wire up collapse/expand toggle
        def _toggle(w=sec_widget, btn=collapse_btn, tb=table, tl=total_label, ab=add_btn):
            w._collapsed = not w._collapsed
            collapsed = w._collapsed
            tb.setVisible(not collapsed)
            tl.setVisible(not collapsed)
            ab.setVisible(not collapsed)
            btn.setText("▸" if collapsed else "▾")
        collapse_btn.clicked.connect(_toggle)

        self._sections.append(sec_widget)
        return sec_widget

    def _cell(self, widget, margins=3) -> QWidget:
        """Wrap an input so it stretches to fill the table cell (avoids clipping)."""
        cell = QWidget()
        lay = QHBoxLayout(cell)
        lay.setContentsMargins(margins, margins, margins, margins)
        lay.setSpacing(0)
        lay.addWidget(widget, 1)
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
        size_lay = QHBoxLayout(size_cell)
        size_lay.setContentsMargins(3, 3, 3, 3)
        size_lay.setSpacing(4)
        size_lay.addWidget(size, 1); size_lay.addWidget(sbtn)
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
        act_lay = QHBoxLayout(act_cell)
        act_lay.setContentsMargins(2, 3, 2, 3)
        act_lay.setSpacing(1)
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
        upb.setFixedSize(26, 30); dnb.setFixedSize(26, 30)
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

    def _row_icon(self, glyph, tip) -> QPushButton:
        b = QPushButton(glyph)
        b.setObjectName("rowIconButton")
        b.setCursor(Qt.PointingHandCursor)
        b.setToolTip(tip)
        b.setFixedSize(30, 30)
        return b

    # ===================== PART D+E: Event filter — DnD + keyboard shortcuts
    _FIELD_ORDER = ["desc", "size", "qty", "rate", "amt"]

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

            # Enter → move to next row / create new row at end
            if key in (Qt.Key_Return, Qt.Key_Enter):
                for gi, wd in self._row_widgets.items():
                    if obj in (wd["desc"], wd["size"], wd["qty"], wd["rate"], wd["amt"]):
                        self._active_gi = gi
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
        elif ev.type() == QEvent.ContextMenu:
            if hasattr(obj, '_drag_row'):  # It's our table
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
        menu.setStyleSheet(
            "QMenu { background: white; border: 1px solid #D7DEE9; border-radius: 8px; padding: 4px; }"
            "QMenu::item { padding: 8px 20px; border-radius: 6px; }"
            "QMenu::item:selected { background: #EFF3FA; color: #173560; }"
        )
        area = self._items[gi].get("area", "OTHER")

        act_copy = menu.addAction("\u2398  Copy Row  (Ctrl+C)")
        act_copy.triggered.connect(lambda: self._copy_row(gi))
        act_paste = menu.addAction("\u2399  Paste Row  (Ctrl+V)")
        act_paste.triggered.connect(lambda: self._paste_row_after(gi))
        act_paste.setEnabled(self._clipboard is not None)

        menu.addSeparator()

        act_dup = menu.addAction(f"{SYS_EDIT}  Duplicate Row")
        act_dup.triggered.connect(lambda: self._duplicate_row())

        menu.addSeparator()

        act_up = menu.addAction(f"\u25B2  Move Up")
        act_up.triggered.connect(lambda: self._move(-1))
        act_down = menu.addAction(f"\u25BC  Move Down")
        act_down.triggered.connect(lambda: self._move(1))

        menu.addSeparator()

        # Move to another area submenu
        areas = [a.name for a in catalog_service.list_areas() if a.name != "+"]
        other_areas = [a for a in areas if a != area]
        if other_areas:
            move_menu = menu.addMenu(f"\u2192  Move to Area")
            for target_area in other_areas:
                act = move_menu.addAction(target_area)
                act.triggered.connect(lambda _, t=target_area: self._move_to_area(gi, t))

        menu.addSeparator()

        act_del = menu.addAction(f"{SYS_DELETE}  Delete Row")
        act_del.triggered.connect(lambda: self._delete_row(gi))

        menu.exec(global_pos)

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
            area = sw._heading.text().strip("— ")
            amt = area_totals.get(area, 0.0)
            sw._total_label.setText(f"{area} TOTAL   \u20B9 {amt:,.2f}")

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
        self._rebuild_sections()
        self._active_gi = insert_at
        self._mark_dirty()
        w = self._row_widgets.get(insert_at)
        if w:
            w["desc"].setFocus()

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
        self._rebuild_sections()
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
        self._push_undo(f"delete '{desc}'")
        self._items.pop(r)
        self._rebuild_sections()
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
            self._recalc()
            self._mark_dirty()

    def _on_rate_changed(self, gi, text):
        if gi < len(self._items):
            self._items[gi]["rate_raw"] = text
            self._recalc()
            self._mark_dirty()

    def _on_amount_changed(self, gi, text):
        if gi < len(self._items):
            self._items[gi]["amount"] = text
            self._recalc()
            self._mark_dirty()

    def _on_gst_toggled(self, checked):
        self.f_gst.setEnabled(bool(checked))
        self._recalc()

    def _apply_discount_pct(self, pct):
        """Apply a percentage discount based on current subtotal."""
        computed, subtotal = calc.compute_rows(self._items)
        disc = round(subtotal * pct / 100.0, 2)
        self.f_discount.setValue(disc)
        self._mark_dirty()
        show_toast(self, f"{pct}% discount applied (\u20B9 {disc:,.2f})", "info")

    # ============================================================ calc
    def _recalc(self):
        computed, subtotal = calc.compute_rows(self._items)
        disc = self.f_discount.value()
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
            numeric = calc.is_number(q) and calc.is_number(rt)
            try:
                w["amt"].setReadOnly(numeric)
            except Exception:
                numeric = False
            if numeric and amt is not None:
                old = w["amt"].text()
                new = _fmt(amt)
                if old != new:
                    w["amt"].setText(new)

        self._sum_row_set(self.l_subtotal, _money(totals["subtotal"]))
        self._sum_row_set(self.l_discount, "-\u20B9 {:,.2f}".format(totals["discount"]))
        self._sum_row_set(self.l_taxable, _money(taxable))
        if self.cb_gst.isChecked():
            self._sum_row_set(self.l_gst, _money(totals["gst_amount"]))
            self.l_gst.setVisible(True)
        else:
            self._sum_row_set(self.l_gst, "\u20B9 0.00")
            self.l_gst.setVisible(False)

        self.l_grand.setText(_money(totals["grand_total"]))
        self.l_words.setText(calc.amount_in_words(totals["grand_total"]))
        self._update_area_totals(area_totals)

    # ============================================================ save
    def _save(self, status):
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

        data = {
            "customer_id": cid,
            "project_id": None,
            "invoice_date": self.f_date.date().toPython(),
            "due_date": self.f_due.date().toPython(),
            "site_address": self.f_site_addr.text().strip(),
            "discount": self.f_discount.value(),
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
                except Exception:  # noqa: BLE001
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
                             editor: "InvoiceEditor") -> QLineEdit:
    """Searchable + custom-entry description with area-aware autocomplete.

    Shows matching items grouped by area, with an "＋ Add custom item" option
    when the typed text doesn't match any existing item. Free-typing is always
    allowed — the custom item option is just a convenience hint.
    """
    from PySide6.QtCore import QStringListModel, QEvent, QObject
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

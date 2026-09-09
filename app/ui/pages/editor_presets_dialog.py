"""Quick Furniture & Interior Presets Catalog.

Provides 1-click insertion of common furniture pieces (beds, wardrobes, modular
kitchen cabinets, sofas, dining, TV units) with standard dimensions and typical
rates into the active invoice area.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

FURNITURE_PRESETS = [
    # --- LIVING ROOM ---
    {"category": "LIVING ROOM", "name": "3-Seater Fabric Sofa", "size": "7'0\" × 3'0\"", "qty": "1", "rate": "24000"},
    {"category": "LIVING ROOM", "name": "L-Shape Premium Italian Leather Sofa", "size": "10'0\" × 7'0\"", "qty": "1", "rate": "65000"},
    {"category": "LIVING ROOM", "name": "TV Entertainment Unit with Back Paneling", "size": "8'0\" × 6'0\"", "qty": "48", "rate": "850"},
    {"category": "LIVING ROOM", "name": "Center Coffee Table with Toughened Glass Top", "size": "4'0\" × 2'6\"", "qty": "1", "rate": "8500"},
    {"category": "LIVING ROOM", "name": "Shoe Rack with Seating Cushion & Drawer", "size": "4'0\" × 3'6\"", "qty": "1", "rate": "12500"},
    {"category": "LIVING ROOM", "name": "CNC Cutting Wooden Foyer Partition", "size": "4'0\" × 8'0\"", "qty": "32", "rate": "650"},
    {"category": "LIVING ROOM", "name": "Decorative Wall Paneling with LED Profile", "size": "10'0\" × 8'0\"", "qty": "80", "rate": "420"},
    {"category": "LIVING ROOM", "name": "Accent Console Table with Brass Metal Inlay", "size": "4'6\" × 1'4\"", "qty": "1", "rate": "16500"},

    # --- MASTER BEDROOM ---
    {"category": "MASTER BEDROOM", "name": "King Size Hydraulic Storage Bed with Headboard", "size": "6'0\" × 6'6\"", "qty": "1", "rate": "48000"},
    {"category": "MASTER BEDROOM", "name": "Queen Size Box Storage Bed with Tufted Cushion", "size": "5'0\" × 6'6\"", "qty": "1", "rate": "38000"},
    {"category": "MASTER BEDROOM", "name": "3-Door Sliding Wardrobe with Lacquered Glass", "size": "7'0\" × 7'0\"", "qty": "49", "rate": "1650"},
    {"category": "MASTER BEDROOM", "name": "4-Door Hinged Wardrobe with Loft Overhead", "size": "8'0\" × 9'0\"", "qty": "72", "rate": "1450"},
    {"category": "MASTER BEDROOM", "name": "Dressing Table with Full-Length LED Mirror & Drawers", "size": "3'0\" × 6'6\"", "qty": "1", "rate": "16000"},
    {"category": "MASTER BEDROOM", "name": "Bedside Tables with Soft-Close Drawers (Pair)", "size": "1'6\" × 1'6\"", "qty": "2", "rate": "4500"},
    {"category": "MASTER BEDROOM", "name": "Study Table with Wall-Hung Bookcase & Storage", "size": "4'6\" × 6'0\"", "qty": "1", "rate": "19500"},

    # --- MODULAR KITCHEN ---
    {"category": "KITCHEN", "name": "Base Cabinets (BWP Marine Ply + Acrylic Shutters)", "size": "10 Rft", "qty": "10", "rate": "2400"},
    {"category": "KITCHEN", "name": "Overhead Wall Cabinets with Tinted Profile Glass", "size": "10 Rft", "qty": "10", "rate": "1900"},
    {"category": "KITCHEN", "name": "Tall Pantry Unit with SS Tandem Pullout Baskets", "size": "2'0\" × 7'0\"", "qty": "1", "rate": "32000"},
    {"category": "KITCHEN", "name": "Breakfast Counter with Solid Wood Top & Footrest", "size": "5'0\" × 2'0\"", "qty": "1", "rate": "14500"},
    {"category": "KITCHEN", "name": "Loft Overhead Storage Cabinets (Waterproof Finish)", "size": "10 Rft", "qty": "10", "rate": "1200"},

    # --- DINING & POOJA ---
    {"category": "DINING", "name": "6-Seater Solid Sheesham Dining Table with Upholstered Chairs", "size": "5'6\" × 3'0\"", "qty": "1", "rate": "42000"},
    {"category": "DINING", "name": "4-Seater Compact Dining Table with Cushion Chairs", "size": "4'0\" × 3'0\"", "qty": "1", "rate": "26000"},
    {"category": "DINING", "name": "Crockery Display Unit with Toughened Glass & Warm LED", "size": "4'0\" × 6'6\"", "qty": "1", "rate": "28000"},
    {"category": "POOJA ROOM", "name": "Wooden Mandir / Pooja Unit with CNC Jaali & Brass Bells", "size": "3'0\" × 5'0\"", "qty": "1", "rate": "22000"},
    {"category": "BALCONY", "name": "Balcony Weatherproof Storage Unit with Louvered Doors", "size": "4'0\" × 4'0\"", "qty": "1", "rate": "13500"},
]


class FurniturePresetsDialog(QDialog):
    """Dialog allowing users to quickly pick furniture items into their invoice."""

    def __init__(self, target_area: str = "", on_select=None, parent=None):
        super().__init__(parent)
        self.target_area = (target_area or "LIVING ROOM").strip().upper()
        self.on_select = on_select
        self.setWindowTitle("⚡ Quick Furniture & Interior Presets")
        self.resize(780, 520)
        self.setMinimumSize(640, 420)

        v = QVBoxLayout(self)
        v.setSpacing(10)
        v.setContentsMargins(16, 14, 16, 14)

        # Header
        h_top = QHBoxLayout()
        title = QLabel("⚡ Quick Furniture Item Presets")
        title.setStyleSheet("font-size: 16px; font-weight: 800; color: #173560;")
        h_top.addWidget(title)
        h_top.addStretch(1)

        self.f_search = QLineEdit()
        self.f_search.setPlaceholderText("🔍 Search furniture (sofa, wardrobe, bed, kitchen...)")
        self.f_search.setClearButtonEnabled(True)
        self.f_search.setFixedWidth(280)
        self.f_search.textChanged.connect(self._filter_items)
        h_top.addWidget(self.f_search)
        v.addLayout(h_top)

        # Category Chips
        self.cats = ["ALL", "LIVING ROOM", "MASTER BEDROOM", "KITCHEN", "DINING", "POOJA ROOM", "BALCONY"]
        self.active_cat = "ALL"
        h_chips = QHBoxLayout()
        h_chips.setSpacing(6)
        self._chip_btns = {}

        for cat in self.cats:
            b = QPushButton(cat)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, c=cat: self._set_category(c))
            h_chips.addWidget(b)
            self._chip_btns[cat] = b
        h_chips.addStretch(1)
        v.addLayout(h_chips)

        # Items Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ROOM / AREA", "ITEM DESCRIPTION", "DEFAULT SIZE", "QTY", "RATE (₹)"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setStyleSheet(
            "QTableWidget { border: 1px solid #CBD5E1; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: #1E293B; color: white; font-weight: 700; padding: 6px; border: none; }"
            "QTableWidget::item:selected { background: #DBEAFE; color: #1E3A8A; }"
        )
        self.table.cellDoubleClicked.connect(lambda r, _: self._insert_row(r))
        v.addWidget(self.table, 1)

        # Footer Actions
        h_foot = QHBoxLayout()
        hint = QLabel("💡 Tip: Double-click any item to insert it directly into your invoice.")
        hint.setStyleSheet("color: #64748B; font-size: 11px;")
        h_foot.addWidget(hint)
        h_foot.addStretch(1)

        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        h_foot.addWidget(btn_close)

        btn_insert = QPushButton("✓ Insert Selected Item")
        btn_insert.setCursor(Qt.PointingHandCursor)
        btn_insert.setStyleSheet(
            "QPushButton { background: #2563EB; color: white; font-weight: 700; padding: 6px 16px; border-radius: 6px; }"
            "QPushButton:hover { background: #1D4ED8; }"
        )
        btn_insert.clicked.connect(self._insert_selected)
        h_foot.addWidget(btn_insert)

        v.addLayout(h_foot)

        self._filtered_list = list(FURNITURE_PRESETS)
        self._update_chip_styles()
        self._refresh_table()

    def _set_category(self, cat: str):
        self.active_cat = cat
        self._update_chip_styles()
        self._filter_items()

    def _update_chip_styles(self):
        for c, b in self._chip_btns.items():
            if c == self.active_cat:
                b.setStyleSheet("background: #173560; color: white; font-weight: 700; border-radius: 12px; padding: 4px 10px;")
            else:
                b.setStyleSheet("background: #F1F5F9; color: #334155; font-weight: 600; border: 1px solid #CBD5E1; border-radius: 12px; padding: 4px 10px;")

    def _filter_items(self):
        query = self.f_search.text().strip().lower()
        results = []
        for p in FURNITURE_PRESETS:
            if self.active_cat != "ALL" and p["category"] != self.active_cat:
                continue
            if query and (query not in p["name"].lower() and query not in p["category"].lower()):
                continue
            results.append(p)
        self._filtered_list = results
        self._refresh_table()

    def _refresh_table(self):
        self.table.setRowCount(len(self._filtered_list))
        for r, item in enumerate(self._filtered_list):
            c_cat = QTableWidgetItem(item["category"])
            c_cat.setTextAlignment(Qt.AlignCenter)
            c_desc = QTableWidgetItem(item["name"])
            f = c_desc.font()
            f.setBold(True)
            c_desc.setFont(f)
            c_size = QTableWidgetItem(item["size"])
            c_size.setTextAlignment(Qt.AlignCenter)
            c_qty = QTableWidgetItem(item["qty"])
            c_qty.setTextAlignment(Qt.AlignCenter)
            c_rate = QTableWidgetItem(f"₹ {float(item['rate']):,.0f}")
            c_rate.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            self.table.setItem(r, 0, c_cat)
            self.table.setItem(r, 1, c_desc)
            self.table.setItem(r, 2, c_size)
            self.table.setItem(r, 3, c_qty)
            self.table.setItem(r, 4, c_rate)

        if self._filtered_list:
            self.table.selectRow(0)

    def _insert_selected(self):
        r = self.table.currentRow()
        if 0 <= r < len(self._filtered_list):
            self._insert_row(r)

    def _insert_row(self, r: int):
        if 0 <= r < len(self._filtered_list):
            item = self._filtered_list[r]
            if self.on_select:
                area = self.target_area if self.target_area else item["category"]
                self.on_select(area, item["name"], item["size"], item["qty"], item["rate"])
            self.accept()

"""Global stylesheet for the modern SaaS-style UI."""
from __future__ import annotations

# Theme palette
PRIMARY = "#2563EB"
PRIMARY_HOVER = "#1D4ED8"
PRIMARY_LIGHT = "#DBEAFE"
BG = "#F4F6FB"
SIDEBAR_BG = "#111827"
SIDEBAR_ACTIVE = "#1F2937"
TEXT = "#1F2937"
TEXT_MUTED = "#6B7280"
BORDER = "#E5E7EB"
WHITE = "#FFFFFF"
SUCCESS = "#059669"
WARNING = "#D97706"
DANGER = "#DC2626"

# Premium invoice-theme palette (navy + gold)
NAVY = "#173560"
NAVY_DARK = "#0F2547"
NAVY_LIGHTER = "#1E4B85"
GOLD = "#C7A24B"
GOLD_DARK = "#A8852F"
GOLD_LIGHT = "#E6D9B8"
NAVY_BG = "#EFF3FA"
NAVY_BORDER = "#C8D2E6"

STYLESHEET = f"""
* {{
    font-family: "Segoe UI", "Segoe UI Variable", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}

QMainWindow {{
    background: {BG};
}}

QWidget#rootWidget {{
    background: {BG};
}}

/* ---------- Sidebar ---------- */
QFrame#sidebar {{
    background: {SIDEBAR_BG};
}}
QLabel#brandTitle {{
    color: {WHITE};
    font-size: 16px;
    font-weight: 700;
}}
QLabel#brandSub {{
    color: #9CA3AF;
    font-size: 11px;
}}
QPushButton#navButton {{
    background: transparent;
    color: #D1D5DB;
    border: none;
    border-radius: 8px;
    text-align: left;
    padding: 11px 16px;
    font-weight: 500;
}}
QPushButton#navButton:hover {{
    background: {SIDEBAR_ACTIVE};
    color: {WHITE};
}}
QPushButton#navButton:checked {{
    background: {PRIMARY};
    color: {WHITE};
    font-weight: 600;
}}

/* ---------- Header ---------- */
QFrame#header {{
    background: {WHITE};
    border-bottom: 1px solid {BORDER};
}}
QLabel#pageTitle {{
    font-size: 18px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#pageSub {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}

/* ---------- Buttons ---------- */
QPushButton {{
    background: {WHITE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
}}
QPushButton:hover {{
    border-color: {PRIMARY};
    color: {PRIMARY};
}}
QPushButton:disabled {{
    color: #9CA3AF;
    border-color: {BORDER};
    background: #F3F4F6;
}}
QPushButton#backButton {{
    background: transparent;
    border: 1px solid {BORDER};
    color: {TEXT};
    padding: 7px 12px;
    font-weight: 600;
    border-radius: 8px;
}}
QPushButton#backButton:hover {{
    background: #F3F4F6;
    border-color: {PRIMARY};
    color: {PRIMARY};
}}
QPushButton#primaryButton {{
    background: {PRIMARY};
    color: {WHITE};
    border: none;
}}
QPushButton#primaryButton:hover {{
    background: {PRIMARY_HOVER};
    color: {WHITE};
}}
QPushButton#dangerButton {{
    background: {DANGER};
    color: {WHITE};
    border: none;
}}
QPushButton#successButton {{
    background: {SUCCESS};
    color: {WHITE};
    border: none;
}}
QPushButton#ghostButton {{
    background: transparent;
    border: none;
    color: {PRIMARY};
}}
QPushButton#navButton {{
    background: transparent;
}}
QPushButton#iconButton {{
    background: transparent;
    border: none;
    padding: 6px;
    font-size: 16px;
}}

/* ---------- Forms ---------- */
QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit {{
    background: {WHITE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: {PRIMARY};
}}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus {{
    border-color: {PRIMARY};
}}
QLabel#fieldLabel {{
    color: {TEXT_MUTED};
    font-size: 12px;
    font-weight: 600;
}}

/* ---------- Cards ---------- */
QFrame#card {{
    background: {WHITE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QLabel#statValue {{
    font-size: 24px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#statLabel {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel#cardTitle {{
    font-size: 15px;
    font-weight: 700;
}}

/* ---------- Tables ---------- */
QTableView {{
    background: {WHITE};
    alternate-background-color: #F9FAFB;
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    selection-background-color: {PRIMARY_LIGHT};
    selection-color: {TEXT};
}}
QTableView::item {{
    padding: 6px 8px;
}}
QHeaderView::section {{
    background: #F3F4F6;
    color: {TEXT_MUTED};
    font-weight: 600;
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 8px;
}}
QTableCornerButton::section {{
    background: #F3F4F6;
    border: none;
}}

/* ---------- Tabs ---------- */
QTabWidget::pane {{
    border: none;
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 8px 18px;
    border-bottom: 2px solid transparent;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    color: {PRIMARY};
    border-bottom: 2px solid {PRIMARY};
    font-weight: 600;
}}
QTabBar::tab:hover {{
    color: {PRIMARY};
}}

/* ---------- Scrollbars ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: #D1D5DB;
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: #D1D5DB;
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ---------- Status / toast ---------- */
QFrame#toast {{
    background: {TEXT};
    border-radius: 10px;
}}
QLabel#toastLabel {{
    color: {WHITE};
    font-weight: 500;
}}
QFrame#toastSuccess {{ background: {SUCCESS}; }}
QFrame#toastError {{ background: {DANGER}; }}

/* ---------- Empty states ---------- */
QLabel#emptyTitle {{
    color: {TEXT};
    font-size: 15px;
    font-weight: 600;
}}
QLabel#emptySub {{
    color: {TEXT_MUTED};
}}

/* ---------- Dialogs ---------- */
QDialog {{
    background: {WHITE};
}}
QLabel#dialogTitle {{
    font-size: 16px;
    font-weight: 700;
}}

/* ---------- Menu / combo dropdown ---------- */
QMenu {{
    background: {WHITE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 16px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {PRIMARY_LIGHT};
    color: {PRIMARY};
}}
QComboBox QAbstractItemView {{
    background: {WHITE};
    border: 1px solid {BORDER};
    selection-background-color: {PRIMARY_LIGHT};
    selection-color: {TEXT};
}}

/* ---------- Progress ---------- */
QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    background: {WHITE};
    text-align: center;
}}
QProgressBar::chunk {{
    background: {PRIMARY};
    border-radius: 5px;
}}

/* ---------- Invoice Editor (navy + gold) ---------- */
QFrame#editorSection {{
    background: {WHITE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QLabel#editorSectionTitle {{
    color: {NAVY};
    font-size: 14px;
    font-weight: 700;
}}
QLabel#validateDot {{
    color: {SUCCESS};
    font-weight: 700;
}}
QFrame#editorToolbar {{
    background: transparent;
    border: none;
}}
/* item table row widgets -> make inputs feel larger / airier */
QTableWidget {{
    background: {WHITE};
    alternate-background-color: #FAFBFD;
    border: 1px solid {NAVY_BORDER};
    border-radius: 10px;
    gridline-color: #EEF1F6;
    selection-background-color: {NAVY_BG};
    selection-color: {TEXT};
}}
QTableWidget::item {{
    padding: 9px 10px;
    border: none;
}}
QTableWidget::item:focus {{
    background: {NAVY_BG};
}}
QHeaderView::section {{
    background: {NAVY};
    color: {WHITE};
    font-weight: 600;
    font-size: 12px;
    padding: 9px 10px;
    border: none;
    border-right: 1px solid {NAVY_LIGHTER};
}}
QTableCornerButton::section {{
    background: {NAVY};
    border: none;
}}
/* summary panel */
QFrame#summaryPanel {{
    background: {NAVY};
    border-radius: 14px;
}}
QLabel#summaryTitle {{
    color: {GOLD_LIGHT};
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#summaryRowLabel {{
    color: #C9D6EA;
    font-size: 13px;
}}
QLabel#summaryRowValue {{
    color: {WHITE};
    font-size: 13px;
    font-weight: 600;
}}
QLabel#grandTotalValue {{
    color: {GOLD};
    font-size: 26px;
    font-weight: 800;
}}
QLabel#grandTotalLabel {{
    color: {GOLD_LIGHT};
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 2px;
}}
QLabel#wordsValue {{
    color: #C9D6EA;
    font-size: 12px;
    font-style: italic;
}}
QFrame#summaryDivider {{
    background: rgba(255,255,255,0.14);
}}
/* per-row measurement/trash icon buttons */
QPushButton#rowIconButton {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 5px;
    font-size: 16px;
}}
QPushButton#rowIconButton:hover {{
    background: {NAVY_BG};
}}
QPushButton#rowDeleteButton {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 5px;
    font-size: 16px;
    color: {DANGER};
}}
QPushButton#rowDeleteButton:hover {{
    background: #FEE2E2;
    color: #B91C1C;
}}
QLabel#areaTotalBar {{
    background: {NAVY_BG};
    border: 1px solid {NAVY_BORDER};
    border-radius: 8px;
    padding: 7px 12px;
    color: {NAVY};
    font-weight: 700;
    font-size: 12px;
}}

/* ---------- area-driven sections (reference billing UI) ---------- */
QFrame#areaSection {{
    background: {WHITE};
    border: 1px solid {NAVY_BORDER};
    border-radius: 12px;
    padding: 14px;
}}
QLabel#areaHeading {{
    color: {WHITE};
    background: {NAVY};
    border-radius: 7px;
    padding: 6px 14px;
    font-size: 14px;
    font-weight: 800;
    letter-spacing: 1px;
}}
QLabel#areaCountBadge {{
    color: {NAVY};
    background: {NAVY_BG};
    border: 1px solid {NAVY_BORDER};
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 700;
}}
QLabel#areaTotalHeading {{
    color: {NAVY};
    font-size: 13px;
    font-weight: 800;
}}
QPushButton#rowEditButton {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 5px;
    font-size: 16px;
    color: {NAVY};
}}
QPushButton#rowEditButton:hover {{
    background: {NAVY_BG};
}}
"""

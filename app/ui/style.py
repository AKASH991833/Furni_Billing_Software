"""Global stylesheet for the modern SaaS-style UI with enhanced glassmorphism."""
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

# Enhanced Glassmorphism + Depth palette
GLASS_BG = "rgba(255, 255, 255, 0.72)"
GLASS_BG_SOLID = "rgba(255, 255, 255, 0.88)"
GLASS_BORDER = "rgba(255, 255, 255, 0.45)"
GLASS_BORDER_DARK = "rgba(23, 53, 96, 0.12)"

# Enhanced depth shadows (layered for realism)
DEPTH_SHADOW_LIGHT = "0 1px 2px rgba(0, 0, 0, 0.04), 0 2px 4px rgba(0, 0, 0, 0.04), 0 4px 8px rgba(0, 0, 0, 0.06)"
DEPTH_SHADOW_MEDIUM = "0 2px 4px rgba(0, 0, 0, 0.04), 0 4px 8px rgba(0, 0, 0, 0.06), 0 8px 16px rgba(0, 0, 0, 0.08), 0 16px 32px rgba(0, 0, 0, 0.06)"
DEPTH_SHADOW_HEAVY = "0 4px 8px rgba(0, 0, 0, 0.06), 0 8px 16px rgba(0, 0, 0, 0.08), 0 16px 32px rgba(0, 0, 0, 0.1), 0 32px 64px rgba(0, 0, 0, 0.08)"
DEPTH_SHADOW_FROSTED = "0 1px 1px rgba(255, 255, 255, 0.8) inset, 0 2px 4px rgba(0, 0, 0, 0.04), 0 4px 8px rgba(0, 0, 0, 0.06), 0 8px 16px rgba(0, 0, 0, 0.06)"

# Frosted glass gradients (multi-stop for light refraction)
GLASS_FROSTED_LIGHT = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,0.95), stop:0.3 rgba(255,255,255,0.88), stop:0.7 rgba(248,250,254,0.85), stop:1 rgba(245,247,252,0.82))"
GLASS_FROSTED_MEDIUM = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,0.92), stop:0.25 rgba(252,253,255,0.86), stop:0.5 rgba(248,250,254,0.82), stop:0.75 rgba(245,247,252,0.78), stop:1 rgba(241,243,249,0.75))"
GLASS_FROSTED_DEEP = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,0.88), stop:0.2 rgba(248,250,254,0.82), stop:0.5 rgba(243,245,250,0.76), stop:0.8 rgba(238,240,247,0.72), stop:1 rgba(235,238,245,0.68))"
GLASS_SIDEBAR = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(17,24,39,0.98), stop:0.5 rgba(15,20,32,0.95), stop:1 rgba(11,16,27,0.92))"
GLASS_INPUT = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,0.95), stop:0.5 rgba(252,253,255,0.92), stop:1 rgba(248,250,254,0.88))"
GLASS_INPUT_FOCUS = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,1.0), stop:0.5 rgba(255,255,255,0.98), stop:1 rgba(252,253,255,0.95))"
GLASS_HOVER_GLOW = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,0.98), stop:0.5 rgba(255,255,255,0.95), stop:1 rgba(252,253,255,0.92))"
GLASS_BUTTON = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,0.92), stop:0.5 rgba(255,255,255,0.88), stop:1 rgba(248,250,254,0.85))"
GLASS_BUTTON_HOVER = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,0.98), stop:0.5 rgba(255,255,255,0.95), stop:1 rgba(255,255,255,0.92))"

# Gradient accents
GRADIENT_NAVY = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0F2547, stop:0.5 #173560, stop:1 #1E4B85)"
GRADIENT_GOLD = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #A8852F, stop:0.5 #C7A24B, stop:1 #D4AF5A)"
GRADIENT_GLASS = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,0.9), stop:1 rgba(255,255,255,0.7))"
GRADIENT_PRIMARY = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:0.5 #3B82F6, stop:1 #60A5FA)"
GRADIENT_PRIMARY_HOVER = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:0.5 #2563EB, stop:1 #3B82F6)"
GRADIENT_SUCCESS = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:0.5 #10B981, stop:1 #34D399)"
GRADIENT_DANGER = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #DC2626, stop:0.5 #EF4444, stop:1 #F87171)"

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
    background: {GLASS_SIDEBAR};
    border-right: 1px solid rgba(255, 255, 255, 0.06);
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
    background: rgba(255, 255, 255, 0.08);
    color: {WHITE};
}}
QPushButton#navButton:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {PRIMARY}, stop:1 #3B82F6);
    color: {WHITE};
    font-weight: 600;
}}

/* ---------- Header ---------- */
QFrame#header {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,0.98), stop:1 rgba(248,250,254,0.95));
    border-bottom: 1px solid rgba(200, 210, 230, 0.5);
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
    background: {GLASS_BUTTON};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: {GLASS_BUTTON_HOVER};
    border-color: rgba(37, 99, 235, 0.3);
    color: {PRIMARY};
}}
QPushButton:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(243,245,250,0.95), stop:1 rgba(237,240,247,0.92));
}}
QPushButton:disabled {{
    color: #9CA3AF;
    border-color: rgba(200, 210, 230, 0.4);
    background: rgba(243, 244, 246, 0.5);
}}
QPushButton#backButton {{
    background: transparent;
    border: 1px solid rgba(200, 210, 230, 0.5);
    color: {TEXT};
    padding: 7px 12px;
    font-weight: 600;
    border-radius: 8px;
}}
QPushButton#backButton:hover {{
    background: {GLASS_BUTTON_HOVER};
    border-color: rgba(37, 99, 235, 0.3);
    color: {PRIMARY};
}}
QPushButton#primaryButton {{
    background: {GRADIENT_PRIMARY};
    color: {WHITE};
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 6px 14px;
}}
QPushButton#primaryButton:hover {{
    background: {GRADIENT_PRIMARY_HOVER};
    color: {WHITE};
}}
QPushButton#dangerButton {{
    background: {GRADIENT_DANGER};
    color: {WHITE};
    border: none;
    border-radius: 8px;
}}
QPushButton#successButton {{
    background: {GRADIENT_SUCCESS};
    color: {WHITE};
    border: none;
    border-radius: 8px;
}}
QPushButton#ghostButton {{
    background: transparent;
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 8px;
    color: {DANGER};
    font-weight: 500;
    padding: 5px 12px;
}}
QPushButton#ghostButton:hover {{
    background: rgba(220, 38, 38, 0.06);
    border-color: rgba(220, 38, 38, 0.3);
}}
QPushButton#iconButton {{
    background: transparent;
    border: none;
    padding: 6px;
    font-size: 16px;
}}

/* ---------- Forms ---------- */
QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit {{
    background: {GLASS_INPUT};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: {PRIMARY};
}}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus {{
    background: {GLASS_INPUT_FOCUS};
    border: 1.5px solid {PRIMARY};
}}
QLabel#fieldLabel {{
    color: {TEXT_MUTED};
    font-size: 12px;
    font-weight: 600;
}}

/* ---------- Cards (Frosted Glass) ---------- */
QFrame#card {{
    background: {GLASS_FROSTED_LIGHT};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 12px;
}}
QFrame#card:hover {{
    border-color: rgba(37, 99, 235, 0.2);
    background: {GLASS_HOVER_GLOW};
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
    background: rgba(255, 255, 255, 0.95);
    alternate-background-color: rgba(248, 250, 254, 0.6);
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 8px;
    gridline-color: rgba(200, 210, 230, 0.4);
    selection-background-color: rgba(37, 99, 235, 0.08);
    selection-color: {TEXT};
}}
QTableView::item {{
    padding: 6px 8px;
}}
QTableView::item:selected {{
    background: rgba(37, 99, 235, 0.1);
}}
QTableView::item:hover {{
    background: rgba(239, 243, 250, 0.6);
}}
QHeaderView::section {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(243,244,246,0.95), stop:1 rgba(237,240,247,0.9));
    color: {TEXT_MUTED};
    font-weight: 600;
    border: none;
    border-right: 1px solid rgba(200, 210, 230, 0.4);
    border-bottom: 1px solid rgba(200, 210, 230, 0.4);
    padding: 8px;
}}
QTableCornerButton::section {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(243,244,246,0.95), stop:1 rgba(237,240,247,0.9));
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
    background: rgba(37, 99, 235, 0.04);
}}

/* ---------- Scrollbars ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: rgba(160, 174, 196, 0.3);
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(160, 174, 196, 0.5);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(160, 174, 196, 0.3);
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: rgba(160, 174, 196, 0.5);
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ---------- Status / toast ---------- */
QFrame#toast {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(31,41,55,0.95), stop:1 rgba(17,24,39,0.92));
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.08);
}}
QLabel#toastLabel {{
    color: {WHITE};
    font-weight: 500;
}}
QFrame#toastSuccess {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(5,150,105,0.95), stop:1 rgba(4,120,87,0.92));
    border: 1px solid rgba(255, 255, 255, 0.1);
}}
QFrame#toastError {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(220,38,38,0.95), stop:1 rgba(185,28,28,0.92));
    border: 1px solid rgba(255, 255, 255, 0.1);
}}

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
    background: {GLASS_FROSTED_LIGHT};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 16px;
}}
QLabel#dialogTitle {{
    font-size: 16px;
    font-weight: 700;
}}

/* ---------- Menu / combo dropdown ---------- */
QMenu {{
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 16px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: rgba(37, 99, 235, 0.08);
    color: {PRIMARY};
}}
QComboBox QAbstractItemView {{
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid rgba(200, 210, 230, 0.5);
    selection-background-color: rgba(37, 99, 235, 0.08);
    selection-color: {TEXT};
}}

/* ---------- Progress ---------- */
QProgressBar {{
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.8);
    text-align: center;
}}
QProgressBar::chunk {{
    background: {GRADIENT_PRIMARY};
    border-radius: 5px;
}}

/* ================================================================
   Invoice Editor — Enhanced Glassmorphism + Depth
   ================================================================ */

/* --- Editor cards (frosted glass) --- */
QFrame#editorSection {{
    background: {GLASS_FROSTED_MEDIUM};
    border: 1px solid rgba(200, 210, 230, 0.45);
    border-radius: 14px;
}}
QFrame#editorSection:hover {{
    border-color: rgba(37, 99, 235, 0.2);
    background: {GLASS_HOVER_GLOW};
}}
QLabel#editorSectionTitle {{
    color: {NAVY};
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}
QLabel#validateDot {{
    color: {SUCCESS};
    font-weight: 700;
}}
QFrame#editorToolbar {{
    background: transparent;
    border: none;
}}

/* --- Invoice detail fields (glass inputs — compact) --- */
QWidget#invoiceEditor QLabel#fieldLabel {{
    color: {TEXT_MUTED};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.6px;
}}
QWidget#invoiceEditor QLineEdit,
QWidget#invoiceEditor QComboBox,
QWidget#invoiceEditor QDateEdit {{
    background: {GLASS_INPUT};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 8px;
    padding: 3px 8px;
    font-size: 11px;
    selection-background-color: {PRIMARY};
}}
QWidget#invoiceEditor QLineEdit:focus,
QWidget#invoiceEditor QComboBox:focus,
QWidget#invoiceEditor QDateEdit:focus {{
    background: {GLASS_INPUT_FOCUS};
    border: 1.5px solid {PRIMARY};
}}
QWidget#invoiceEditor QLineEdit:read-only {{
    background: rgba(243, 244, 246, 0.5);
    color: {TEXT_MUTED};
}}

/* --- Invoice editor internal controls (compact — no horizontal scroll) --- */
QWidget#invoiceEditor QPushButton {{
    padding: 4px 9px;
    font-size: 11px;
    background: {GLASS_BUTTON};
    border: 1px solid rgba(200, 210, 230, 0.5);
}}
QWidget#invoiceEditor QPushButton:hover {{
    background: {GLASS_BUTTON_HOVER};
    border-color: rgba(37, 99, 235, 0.3);
}}
QWidget#invoiceEditor QLineEdit, QWidget#invoiceEditor QComboBox,
QWidget#invoiceEditor QDateEdit, QWidget#invoiceEditor QDoubleSpinBox {{
    padding: 2px 6px;
    font-size: 11px;
}}
/* --- Invoice editor single page scroll (details → items → summary) --- */
QScrollArea#editorPageScroll {{
    background: transparent;
    border: none;
}}
QWidget#editorPageContainer {{
    background: transparent;
}}

/* --- Items & Area card toolbar --- */
QLabel#toolbarGroupLabel {{
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}

/* --- Item tables — Excel-like clear grid --- */
QTableWidget {{
    background: rgba(255, 255, 255, 0.95);
    alternate-background-color: rgba(244, 247, 252, 0.5);
    border: 2px solid rgba(184, 196, 216, 0.7);
    border-radius: 8px;
    gridline-color: rgba(184, 196, 216, 0.6);
    selection-background-color: rgba(219, 234, 254, 0.8);
    selection-color: {TEXT};
    color: {TEXT};
    font-size: 13px;
}}
QTableWidget::item {{
    color: {TEXT};
    padding: 4px 8px;
    border-bottom: 1px solid rgba(184, 196, 216, 0.5);
    border-right: 1px solid rgba(184, 196, 216, 0.5);
}}
QTableWidget::item:selected {{
    background: rgba(219, 234, 254, 0.8);
    color: {TEXT};
}}
QTableWidget::item:focus {{
    background: rgba(239, 243, 250, 0.7);
    color: {TEXT};
}}
QTableWidget::item:hover {{
    background: rgba(232, 238, 247, 0.6);
}}
/* Table inputs — white background, dark navy text, clear border (never invisible) */
QTableWidget QLineEdit {{
    background: {GLASS_INPUT};
    border: 1px solid rgba(203, 213, 225, 0.6);
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 13px;
    color: #172033;
    selection-background-color: {PRIMARY};
    selection-color: {WHITE};
}}
QTableWidget QLineEdit:hover {{
    border-color: rgba(167, 180, 203, 0.8);
}}
QTableWidget QLineEdit:focus {{
    background: {GLASS_INPUT_FOCUS};
    border: 2px solid {PRIMARY};
    border-radius: 4px;
    color: #172033;
    font-size: 13px;
}}
QTableWidget QLineEdit:read-only {{
    background: rgba(243, 245, 249, 0.6);
    color: #172033;
    font-size: 13px;
    font-weight: 600;
}}
/* Table input placeholder text — clearly visible */
QTableWidget QLineEdit::placeholder {{
    color: #94A3B8;
    font-style: italic;
    font-size: 13px;
}}
/* Table header — dark navy with clear column separators */
QHeaderView::section {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {NAVY_DARK}, stop:0.5 {NAVY}, stop:1 {NAVY_LIGHTER});
    color: {WHITE};
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.5px;
    padding: 10px 12px;
    border: none;
    border-right: 1px solid rgba(255, 255, 255, 0.2);
}}
QTableCornerButton::section {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {NAVY_DARK}, stop:1 {NAVY});
    border: none;
}}
/* Scrollbar in tables */
QTableWidget QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px;
}}
QTableWidget QScrollBar::handle:vertical {{
    background: rgba(160, 174, 196, 0.3);
    border-radius: 4px;
    min-height: 24px;
}}
QTableWidget QScrollBar::handle:vertical:hover {{
    background: rgba(160, 174, 196, 0.5);
}}

/* --- Summary panel (full-width frosted glass card) --- */
QFrame#summaryPanel {{
    background: {GLASS_FROSTED_DEEP};
    border: 1px solid rgba(203, 213, 225, 0.6);
    border-top: 3px solid {GOLD_DARK};
    border-radius: 14px;
}}
QLabel#summaryTitle {{
    color: {NAVY_DARK};
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 3px;
}}
QLabel#summarySubTitle {{
    color: #64748B;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
}}
QLabel#summaryFieldLabel {{
    color: #475569;
    font-size: 12px;
    font-weight: 700;
}}
QFrame#summaryStat {{
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid rgba(215, 222, 233, 0.6);
    border-radius: 10px;
    border-top: 2px solid rgba(23, 53, 96, 0.15);
}}
QLineEdit#summaryTextInput {{
    background: {GLASS_INPUT};
    border: 1px solid rgba(203, 213, 225, 0.6);
    border-radius: 8px;
    padding: 6px 10px;
    color: #172033;
    font-size: 12px;
    selection-background-color: {PRIMARY};
    selection-color: {WHITE};
}}
QLineEdit#summaryTextInput:focus {{
    background: {GLASS_INPUT_FOCUS};
    border: 2px solid {PRIMARY};
}}
QLineEdit#summaryTextInput::placeholder {{
    color: #94A3B8;
    font-style: italic;
}}
QTextEdit#summaryTextInput {{
    background: {GLASS_INPUT};
    border: 1px solid rgba(203, 213, 225, 0.6);
    border-radius: 8px;
    padding: 6px 10px;
    color: #172033;
    font-size: 12px;
    selection-background-color: {PRIMARY};
    selection-color: {WHITE};
}}
QTextEdit#summaryTextInput:focus {{
    background: {GLASS_INPUT_FOCUS};
    border: 2px solid {PRIMARY};
}}
QTextEdit#summaryTextInput::placeholder {{
    color: #94A3B8;
    font-style: italic;
}}
QFrame#signLine {{
    border-bottom: 2px solid {NAVY};
    border-radius: 0px;
}}
QLabel#summaryRowLabel {{
    color: #64748B;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}
QLabel#summaryRowValue {{
    color: {NAVY_DARK};
    font-size: 14px;
    font-weight: 700;
}}
QFrame#grandTotalBar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {NAVY_DARK}, stop:0.3 {NAVY}, stop:0.7 {NAVY}, stop:1 {NAVY_LIGHTER});
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.1);
}}
QLabel#grandTotalValue {{
    color: {GOLD};
    font-size: 26px;
    font-weight: 800;
    letter-spacing: 0.5px;
}}
QLabel#grandTotalLabel {{
    color: rgba(255, 245, 220, 0.95);
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 3px;
}}
QLabel#wordsValue {{
    color: #64748B;
    font-size: 12px;
    font-style: italic;
}}
QFrame#summaryDivider {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(199, 162, 75, 0.0), stop:0.5 rgba(199, 162, 75, 0.4), stop:1 rgba(199, 162, 75, 0.0));
    max-height: 1px;
}}
QCheckBox#summaryGst {{
    color: {NAVY_DARK};
    font-weight: 700;
    font-size: 13px;
}}
QCheckBox#summaryGst::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 2px solid #94A3B8;
    background: {GLASS_INPUT};
}}
QCheckBox#summaryGst::indicator:checked {{
    background: {NAVY};
    border-color: {NAVY};
}}
QCheckBox#summaryGst::indicator:hover {{
    border-color: {GOLD_DARK};
}}
QDoubleSpinBox#summarySpin {{
    background: {GLASS_INPUT};
    border: 1px solid rgba(203, 213, 225, 0.6);
    border-radius: 8px;
    color: #172033;
    padding: 4px 8px;
    font-size: 13px;
}}
QDoubleSpinBox#summarySpin:focus {{
    background: {GLASS_INPUT_FOCUS};
    border: 2px solid {PRIMARY};
}}
QPushButton#discountPresetBtn {{
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    color: rgba(230, 217, 184, 0.8);
    font-size: 10px;
    font-weight: 700;
    padding: 2px 8px;
}}
QPushButton#discountPresetBtn:hover {{
    background: rgba(199, 162, 75, 0.2);
    border-color: rgba(199, 162, 75, 0.4);
    color: {GOLD};
}}
QPushButton#discountPresetBtn:pressed {{
    background: rgba(199, 162, 75, 0.3);
}}

/* --- Row action buttons (glass) --- */
QPushButton#rowIconButton {{
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 2px;
    font-size: 13px;
    color: {TEXT_MUTED};
}}
QPushButton#rowIconButton:hover {{
    background: rgba(37, 99, 235, 0.08);
    color: {PRIMARY};
}}
QPushButton#rowDeleteButton {{
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 2px;
    font-size: 13px;
    color: #9CA3AF;
}}
QPushButton#rowDeleteButton:hover {{
    background: rgba(220, 38, 38, 0.08);
    color: {DANGER};
}}
QPushButton#rowEditButton {{
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 2px;
    font-size: 13px;
    color: {NAVY};
}}
QPushButton#rowEditButton:hover {{
    background: rgba(23, 53, 96, 0.08);
}}
QFrame#areaTotalBar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(23, 53, 96, 0.04), stop:1 rgba(199, 162, 75, 0.06));
    border: 1px solid rgba(168, 133, 47, 0.3);
    border-radius: 8px;
    padding: 4px 12px;
}}
QLabel#areaTotalName {{
    color: {NAVY_DARK};
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.5px;
}}
QLabel#areaTotalValue {{
    color: {NAVY_DARK};
    font-size: 13px;
    font-weight: 800;
}}

/* --- Area sections (frosted glass depth) --- */
QFrame#areaBanner {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(23, 53, 96, 0.06), stop:0.5 rgba(199, 162, 75, 0.08), stop:1 rgba(23, 53, 96, 0.04));
    border: 1px solid rgba(168, 133, 47, 0.35);
    border-left: 5px solid {GOLD_DARK};
    border-radius: 10px;
}}
QPushButton#areaCollapseBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(23,53,96,0.92), stop:1 rgba(30,75,133,0.88));
    color: {WHITE};
    border: none;
    border-radius: 5px;
    font-size: 12px;
    font-weight: 700;
    padding: 0 6px;
    min-height: 24px;
}}
QPushButton#areaCollapseBtn:hover {{
    background: {NAVY_DARK};
}}
QPushButton#areaAddBtn {{
    background: {GRADIENT_GOLD};
    color: {NAVY_DARK};
    border: none;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 800;
    padding: 4px 12px;
}}
QPushButton#areaAddBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #C7A24B, stop:0.5 #D4AF5A, stop:1 #E6D9B8);
}}
QFrame#areaSection {{
    background: {GLASS_FROSTED_DEEP};
    border: 1px solid rgba(203, 213, 225, 0.5);
    border-radius: 14px;
    border-top: 2px solid rgba(199, 162, 75, 0.25);
}}
QFrame#areaSection:hover {{
    border-color: rgba(199, 162, 75, 0.4);
    border-top-color: rgba(199, 162, 75, 0.5);
}}
/* Vertical splitter between area sections — mouse-draggable resize handles */
QSplitter#areaSplitter::handle {{
    background: transparent;
}}
QSplitter#areaSplitter::handle:vertical {{
    height: 10px;
    background: rgba(23, 53, 96, 0.15);
    border-radius: 5px;
    margin: 0 2px;
    border-bottom: 1px solid rgba(23, 53, 96, 0.2);
}}
QSplitter#areaSplitter::handle:vertical:hover {{
    background: rgba(199, 162, 75, 0.4);
    border-bottom-color: rgba(199, 162, 75, 0.6);
}}
QLabel#areaHeading {{
    color: {NAVY_DARK};
    background: transparent;
    font-size: 16px;
    font-weight: 800;
    letter-spacing: 1px;
    padding: 0 6px;
}}
QLabel#areaCountBadge {{
    color: {NAVY_DARK};
    background: rgba(255, 255, 255, 0.9);
    border: 1px solid rgba(168, 133, 47, 0.4);
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 700;
}}

/* --- Breadcrumb / action bar --- */
QLabel#editorBreadcrumb {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.3px;
}}
QLabel#editorTitle {{
    color: {NAVY};
    font-size: 18px;
    font-weight: 800;
    letter-spacing: -0.3px;
}}
QPushButton#editorSaveBtn {{
    background: {GRADIENT_PRIMARY};
    color: {WHITE};
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 7px 18px;
    font-size: 12px;
}}
QPushButton#editorSaveBtn:hover {{
    background: {GRADIENT_PRIMARY_HOVER};
    color: {WHITE};
}}
QPushButton#editorDraftBtn {{
    background: {GLASS_BUTTON};
    border: 1px solid rgba(200, 210, 230, 0.6);
    border-radius: 8px;
    color: {TEXT_MUTED};
    font-weight: 600;
    padding: 7px 16px;
    font-size: 12px;
}}
QPushButton#editorDraftBtn:hover {{
    background: {GLASS_BUTTON_HOVER};
    border-color: rgba(37, 99, 235, 0.3);
    color: {PRIMARY};
}}
QPushButton#editorBackBtn {{
    background: rgba(255, 255, 255, 0.6);
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 8px;
    color: {TEXT};
    font-weight: 600;
    padding: 7px 14px;
    font-size: 12px;
}}
QPushButton#editorBackBtn:hover {{
    background: {GLASS_BUTTON_HOVER};
    border-color: rgba(23, 53, 96, 0.3);
    color: {NAVY};
}}

/* --- Due date quick presets --- */
QPushButton#duePresetBtn {{
    background: rgba(239, 243, 250, 0.7);
    border: 1px solid rgba(200, 210, 230, 0.4);
    border-radius: 6px;
    color: {NAVY};
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
}}
QPushButton#duePresetBtn:hover {{
    background: rgba(239, 243, 250, 0.9);
    border-color: rgba(23, 53, 96, 0.3);
}}
QPushButton#duePresetBtn:pressed {{
    background: {NAVY};
    color: {WHITE};
}}

/* --- New Area button --- */
QPushButton#newAreaBtn {{
    background: transparent;
    border: 2px dashed rgba(200, 210, 230, 0.5);
    border-radius: 10px;
    color: {TEXT_MUTED};
    font-weight: 600;
    font-size: 12px;
    padding: 10px 24px;
}}
QPushButton#newAreaBtn:hover {{
    border-color: rgba(37, 99, 235, 0.4);
    color: {PRIMARY};
    background: rgba(37, 99, 235, 0.04);
}}

/* --- Item count badge --- */
QLabel#itemCountBadge {{
    color: {NAVY};
    font-size: 11px;
    font-weight: 700;
    background: rgba(239, 243, 250, 0.8);
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 10px;
    padding: 3px 10px;
}}

/* --- Shortcut hints --- */
QLabel#shortcutHint {{
    color: #9CA3AF;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.2px;
}}

/* --- Scroll area (items container) --- */
QScrollArea#areasScroll {{
    background: transparent;
    border: none;
}}


/* ================================================================
   Dashboard — Enhanced Glassmorphism + Depth
   ================================================================ */

/* --- Dashboard stat cards (frosted glass depth) --- */
QFrame#dashStatCard {{
    background: {GLASS_FROSTED_MEDIUM};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 14px;
    border-left: 4px solid {PRIMARY};
}}
QFrame#dashStatCard:hover {{
    border-color: rgba(37, 99, 235, 0.3);
    background: {GLASS_HOVER_GLOW};
}}
QLabel#dashStatValue {{
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -0.3px;
}}
QLabel#dashStatLabel {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.3px;
}}

/* --- Dashboard action buttons (glass) --- */
QPushButton#dashActionPrimary {{
    background: {GRADIENT_PRIMARY};
    color: {WHITE};
    border: none;
    border-radius: 10px;
    padding: 9px 20px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton#dashActionPrimary:hover {{
    background: {GRADIENT_PRIMARY_HOVER};
    color: {WHITE};
}}
QPushButton#dashActionSecondary {{
    background: {GLASS_BUTTON};
    border: 1px solid rgba(200, 210, 230, 0.6);
    border-radius: 10px;
    padding: 9px 20px;
    font-weight: 600;
    font-size: 12px;
    color: {TEXT};
}}
QPushButton#dashActionSecondary:hover {{
    background: {GLASS_BUTTON_HOVER};
    border-color: rgba(37, 99, 235, 0.3);
    color: {PRIMARY};
}}

/* --- Dashboard section cards (frosted glass) --- */
QFrame#dashSectionCard {{
    background: {GLASS_FROSTED_MEDIUM};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 14px;
}}
QFrame#dashSectionCard:hover {{
    border-color: rgba(23, 53, 96, 0.15);
}}
QLabel#dashSectionTitle {{
    color: {NAVY};
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.3px;
}}

/* --- Dashboard tables --- */
QTableWidget#dashTable {{
    background: rgba(255, 255, 255, 0.92);
    alternate-background-color: rgba(239, 243, 250, 0.4);
    border: 1px solid rgba(200, 210, 230, 0.4);
    border-radius: 10px;
    gridline-color: rgba(200, 210, 230, 0.3);
    selection-background-color: rgba(37, 99, 235, 0.08);
}}
QTableWidget#dashTable::item {{
    padding: 7px 10px;
    border-bottom: 1px solid rgba(200, 210, 230, 0.25);
}}
QTableWidget#dashTable::item:selected {{
    background: rgba(37, 99, 235, 0.08);
}}
QTableWidget#dashTable::item:hover {{
    background: rgba(239, 243, 250, 0.5);
}}
QTableWidget#dashTable QHeaderView::section {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(243,244,246,0.9), stop:1 rgba(237,240,247,0.85));
    color: {TEXT_MUTED};
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.3px;
    padding: 9px 10px;
    border: none;
    border-bottom: 1px solid rgba(200, 210, 230, 0.4);
    border-right: 1px solid rgba(200, 210, 230, 0.3);
}}

/* --- Dashboard alert banner (glass danger) --- */
QFrame#dashAlert {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(254, 242, 242, 0.95), stop:1 rgba(254, 226, 226, 0.85));
    border: 1px solid rgba(252, 165, 165, 0.5);
    border-radius: 12px;
    border-left: 4px solid {DANGER};
}}
QLabel#dashAlertText {{
    color: #991B1B;
    font-weight: 600;
    font-size: 12px;
}}


/* ================================================================
   Invoices List — Enhanced Glassmorphism + Depth
   ================================================================ */

/* --- Search bar (glass) --- */
QLineEdit#invoiceSearch {{
    background: {GLASS_INPUT};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 12px;
    selection-background-color: {PRIMARY};
}}
QLineEdit#invoiceSearch:focus {{
    background: {GLASS_INPUT_FOCUS};
    border: 1.5px solid {PRIMARY};
}}

/* --- Status filter dropdown (glass) --- */
QComboBox#invoiceStatusFilter {{
    background: {GLASS_INPUT};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 10px;
    padding: 8px 12px;
    font-size: 12px;
    min-width: 120px;
}}
QComboBox#invoiceStatusFilter:focus {{
    background: {GLASS_INPUT_FOCUS};
    border: 1.5px solid {PRIMARY};
}}

/* --- Invoice list table (frosted glass depth) --- */
QTableWidget#invoiceTable {{
    background: rgba(255, 255, 255, 0.92);
    alternate-background-color: rgba(239, 243, 250, 0.4);
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 12px;
    gridline-color: rgba(200, 210, 230, 0.3);
    selection-background-color: rgba(37, 99, 235, 0.08);
    selection-color: {TEXT};
}}
QTableWidget#invoiceTable::item {{
    padding: 8px 10px;
    border-bottom: 1px solid rgba(200, 210, 230, 0.25);
}}
QTableWidget#invoiceTable::item:selected {{
    background: rgba(37, 99, 235, 0.08);
}}
QTableWidget#invoiceTable::item:hover {{
    background: rgba(239, 243, 250, 0.5);
}}
QTableWidget#invoiceTable QHeaderView::section {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {NAVY_DARK}, stop:0.5 {NAVY}, stop:1 {NAVY_LIGHTER});
    color: {WHITE};
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.5px;
    padding: 10px 12px;
    border: none;
    border-right: 1px solid rgba(255, 255, 255, 0.15);
}}
QTableWidget#invoiceTable QTableCornerButton::section {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {NAVY_DARK}, stop:1 {NAVY});
    border: none;
}}

/* --- Invoice action buttons --- */
QPushButton#invoiceNewBtn {{
    background: {GRADIENT_PRIMARY};
    color: {WHITE};
    border: none;
    border-radius: 10px;
    padding: 9px 22px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton#invoiceNewBtn:hover {{
    background: {GRADIENT_PRIMARY_HOVER};
    color: {WHITE};
}}
QPushButton#invoiceEditBtn {{
    background: {GRADIENT_PRIMARY};
    color: {WHITE};
    border: none;
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton#invoiceEditBtn:hover {{
    background: {GRADIENT_PRIMARY_HOVER};
    color: {WHITE};
}}
QPushButton#invoicePayBtn {{
    background: {GRADIENT_SUCCESS};
    color: {WHITE};
    border: none;
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton#invoicePayBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:0.5 #059669, stop:1 #10B981);
    color: {WHITE};
}}
QPushButton#invoiceActionBtn {{
    background: {GLASS_BUTTON};
    border: 1px solid rgba(200, 210, 230, 0.6);
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
    font-size: 12px;
    color: {TEXT};
}}
QPushButton#invoiceActionBtn:hover {{
    background: {GLASS_BUTTON_HOVER};
    border-color: rgba(37, 99, 235, 0.3);
    color: {PRIMARY};
}}
QPushButton#invoiceActionBtn:disabled {{
    color: #9CA3AF;
    border-color: rgba(200, 210, 230, 0.4);
    background: rgba(243, 244, 246, 0.5);
}}
QToolButton#invoiceToolBtn {{
    background: {GLASS_BUTTON};
    border: 1px solid rgba(200, 210, 230, 0.6);
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
    font-size: 12px;
    color: {TEXT};
}}
QToolButton#invoiceToolBtn:hover {{
    background: {GLASS_BUTTON_HOVER};
    border-color: rgba(37, 99, 235, 0.3);
    color: {PRIMARY};
}}
QToolButton#invoiceToolBtn:disabled {{
    color: #9CA3AF;
    border-color: rgba(200, 210, 230, 0.4);
    background: rgba(243, 244, 246, 0.5);
}}

/* --- Invoice actions bar --- */
QFrame#invoiceActionsBar {{
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(200, 210, 230, 0.4);
    border-radius: 12px;
    padding: 8px 14px;
}}
QLabel#invoiceActionsLabel {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}

/* --- Invoice empty state --- */
QLabel#invoiceEmptyTitle {{
    color: {NAVY};
    font-size: 15px;
    font-weight: 700;
}}
QLabel#invoiceEmptySub {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}

/* ================================================================
   Settings Page — Glassmorphism + Depth
   ================================================================ */

/* --- Settings section cards (frosted glass) --- */
QFrame#settingsSection {{
    background: {GLASS_FROSTED_MEDIUM};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 14px;
}}
QFrame#settingsSection:hover {{
    border-color: rgba(37, 99, 235, 0.2);
    background: {GLASS_HOVER_GLOW};
}}
QLabel#settingsSectionTitle {{
    color: {NAVY};
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.3px;
}}
QLabel#settingsFieldLabel {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.3px;
}}

/* --- Settings form inputs (glass) --- */
QWidget#settingsPage QLineEdit,
QWidget#settingsPage QComboBox,
QWidget#settingsPage QTextEdit,
QWidget#settingsPage QSpinBox,
QWidget#settingsPage QDoubleSpinBox {{
    background: {GLASS_INPUT};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 12px;
    selection-background-color: {PRIMARY};
}}
QWidget#settingsPage QLineEdit:focus,
QWidget#settingsPage QComboBox:focus,
QWidget#settingsPage QTextEdit:focus,
QWidget#settingsPage QSpinBox:focus,
QWidget#settingsPage QDoubleSpinBox:focus {{
    background: {GLASS_INPUT_FOCUS};
    border: 1.5px solid {PRIMARY};
}}
QWidget#settingsPage QLabel#fieldLabel {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
}}

/* --- Settings action buttons (glass) --- */
QPushButton#settingsSaveBtn {{
    background: {GRADIENT_PRIMARY};
    color: {WHITE};
    border: none;
    border-radius: 10px;
    padding: 9px 24px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton#settingsSaveBtn:hover {{
    background: {GRADIENT_PRIMARY_HOVER};
    color: {WHITE};
}}
QPushButton#settingsResetBtn {{
    background: {GLASS_BUTTON};
    border: 1px solid rgba(200, 210, 230, 0.6);
    border-radius: 10px;
    padding: 9px 20px;
    font-weight: 600;
    font-size: 12px;
    color: {TEXT};
}}
QPushButton#settingsResetBtn:hover {{
    background: {GLASS_BUTTON_HOVER};
    border-color: rgba(37, 99, 235, 0.3);
    color: {PRIMARY};
}}

/* --- Settings file picker (glass) --- */
QPushButton#settingsFileBtn {{
    background: {GLASS_BUTTON};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 8px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 600;
    color: {NAVY};
}}
QPushButton#settingsFileBtn:hover {{
    background: {GLASS_BUTTON_HOVER};
    border-color: rgba(37, 99, 235, 0.3);
}}

/* --- Settings preview card (glass) --- */
QFrame#settingsPreview {{
    background: {GLASS_FROSTED_LIGHT};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 12px;
}}
QLabel#settingsPreviewTitle {{
    color: {NAVY};
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}


/* ================================================================
   Reports Page — Glassmorphism + Depth
   ================================================================ */

/* --- Reports section cards (frosted glass) --- */
QFrame#reportsSection {{
    background: {GLASS_FROSTED_MEDIUM};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 14px;
}}
QFrame#reportsSection:hover {{
    border-color: rgba(37, 99, 235, 0.2);
    background: {GLASS_HOVER_GLOW};
}}
QLabel#reportsSectionTitle {{
    color: {NAVY};
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.3px;
}}

/* --- Reports filter bar (glass) --- */
QFrame#reportsFilterBar {{
    background: rgba(255, 255, 255, 0.75);
    border: 1px solid rgba(200, 210, 230, 0.4);
    border-radius: 12px;
    padding: 10px 16px;
}}
QWidget#reportsPage QLineEdit,
QWidget#reportsPage QComboBox,
QWidget#reportsPage QDateEdit {{
    background: {GLASS_INPUT};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 12px;
    selection-background-color: {PRIMARY};
}}
QWidget#reportsPage QLineEdit:focus,
QWidget#reportsPage QComboBox:focus,
QWidget#reportsPage QDateEdit:focus {{
    background: {GLASS_INPUT_FOCUS};
    border: 1.5px solid {PRIMARY};
}}

/* --- Reports action buttons (glass) --- */
QPushButton#reportsGenerateBtn {{
    background: {GRADIENT_PRIMARY};
    color: {WHITE};
    border: none;
    border-radius: 10px;
    padding: 9px 22px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton#reportsGenerateBtn:hover {{
    background: {GRADIENT_PRIMARY_HOVER};
    color: {WHITE};
}}
QPushButton#reportsExportBtn {{
    background: {GLASS_BUTTON};
    border: 1px solid rgba(200, 210, 230, 0.6);
    border-radius: 10px;
    padding: 9px 20px;
    font-weight: 600;
    font-size: 12px;
    color: {TEXT};
}}
QPushButton#reportsExportBtn:hover {{
    background: {GLASS_BUTTON_HOVER};
    border-color: rgba(37, 99, 235, 0.3);
    color: {PRIMARY};
}}

/* --- Reports table (glass) --- */
QTableWidget#reportsTable {{
    background: rgba(255, 255, 255, 0.92);
    alternate-background-color: rgba(239, 243, 250, 0.4);
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 12px;
    gridline-color: rgba(200, 210, 230, 0.3);
    selection-background-color: rgba(37, 99, 235, 0.08);
    selection-color: {TEXT};
}}
QTableWidget#reportsTable::item {{
    padding: 8px 10px;
    border-bottom: 1px solid rgba(200, 210, 230, 0.25);
}}
QTableWidget#reportsTable::item:selected {{
    background: rgba(37, 99, 235, 0.08);
}}
QTableWidget#reportsTable::item:hover {{
    background: rgba(239, 243, 250, 0.5);
}}
QTableWidget#reportsTable QHeaderView::section {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {NAVY_DARK}, stop:0.5 {NAVY}, stop:1 {NAVY_LIGHTER});
    color: {WHITE};
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.5px;
    padding: 10px 12px;
    border: none;
    border-right: 1px solid rgba(255, 255, 255, 0.15);
}}


/* ================================================================
   Customers Page — Glassmorphism + Depth
   ================================================================ */

/* --- Customers section cards (frosted glass) --- */
QFrame#customersSection {{
    background: {GLASS_FROSTED_MEDIUM};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 14px;
}}
QFrame#customersSection:hover {{
    border-color: rgba(37, 99, 235, 0.2);
    background: {GLASS_HOVER_GLOW};
}}
QLabel#customersSectionTitle {{
    color: {NAVY};
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.3px;
}}

/* --- Customers search bar (glass) --- */
QLineEdit#customersSearch {{
    background: {GLASS_INPUT};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 12px;
    selection-background-color: {PRIMARY};
}}
QLineEdit#customersSearch:focus {{
    background: {GLASS_INPUT_FOCUS};
    border: 1.5px solid {PRIMARY};
}}

/* --- Customers action buttons (glass) --- */
QPushButton#customersAddBtn {{
    background: {GRADIENT_PRIMARY};
    color: {WHITE};
    border: none;
    border-radius: 10px;
    padding: 9px 22px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton#customersAddBtn:hover {{
    background: {GRADIENT_PRIMARY_HOVER};
    color: {WHITE};
}}
QPushButton#customersEditBtn {{
    background: {GLASS_BUTTON};
    border: 1px solid rgba(200, 210, 230, 0.6);
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: 600;
    font-size: 12px;
    color: {TEXT};
}}
QPushButton#customersEditBtn:hover {{
    background: {GLASS_BUTTON_HOVER};
    border-color: rgba(37, 99, 235, 0.3);
    color: {PRIMARY};
}}
QPushButton#customersDeleteBtn {{
    background: transparent;
    border: 1px solid rgba(220, 38, 38, 0.3);
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: 600;
    font-size: 12px;
    color: {DANGER};
}}
QPushButton#customersDeleteBtn:hover {{
    background: rgba(220, 38, 38, 0.06);
    border-color: rgba(220, 38, 38, 0.5);
}}
QPushButton#customersViewBtn {{
    background: {GLASS_BUTTON};
    border: 1px solid rgba(200, 210, 230, 0.6);
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: 600;
    font-size: 12px;
    color: {TEXT};
}}
QPushButton#customersViewBtn:hover {{
    background: {GLASS_BUTTON_HOVER};
    border-color: rgba(37, 99, 235, 0.3);
    color: {PRIMARY};
}}

/* --- Customers table (glass) --- */
QTableWidget#customersTable {{
    background: rgba(255, 255, 255, 0.92);
    alternate-background-color: rgba(239, 243, 250, 0.4);
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 12px;
    gridline-color: rgba(200, 210, 230, 0.3);
    selection-background-color: rgba(37, 99, 235, 0.08);
    selection-color: {TEXT};
}}
QTableWidget#customersTable::item {{
    padding: 8px 10px;
    border-bottom: 1px solid rgba(200, 210, 230, 0.25);
}}
QTableWidget#customersTable::item:selected {{
    background: rgba(37, 99, 235, 0.08);
}}
QTableWidget#customersTable::item:hover {{
    background: rgba(239, 243, 250, 0.5);
}}
QTableWidget#customersTable QHeaderView::section {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {NAVY_DARK}, stop:0.5 {NAVY}, stop:1 {NAVY_LIGHTER});
    color: {WHITE};
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.5px;
    padding: 10px 12px;
    border: none;
    border-right: 1px solid rgba(255, 255, 255, 0.15);
}}

/* --- Customers detail card (glass) --- */
QFrame#customerDetail {{
    background: {GLASS_FROSTED_LIGHT};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 14px;
}}
QLabel#customerDetailName {{
    color: {NAVY};
    font-size: 18px;
    font-weight: 800;
}}
QLabel#customerDetailLabel {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
}}
QLabel#customerDetailValue {{
    color: {TEXT};
    font-size: 13px;
    font-weight: 500;
}}

/* --- Customers empty state --- */
QLabel#customersEmptyTitle {{
    color: {NAVY};
    font-size: 15px;
    font-weight: 700;
}}
QLabel#customersEmptySub {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}


/* ================================================================
   Animated Glass Widgets (used by common.py)
   ================================================================ */
QFrame#glassCard {{
    background: {GLASS_FROSTED_LIGHT};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 14px;
}}
QFrame#glassSection {{
    background: {GLASS_FROSTED_MEDIUM};
    border: 1px solid rgba(200, 210, 230, 0.5);
    border-radius: 14px;
}}
"""

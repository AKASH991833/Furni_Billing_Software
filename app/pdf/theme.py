"""PDF theme configuration.

The invoice can be rendered with several built-in colour themes.  Each theme
is an immutable :class:`Theme` dataclass carrying every colour the CSS
generator needs.

Available themes
----------------
* **colour**   – Navy & Gold premium (default)
* **classic**  – Black & White professional
* **modern**   – Teal & Coral fresh
* **minimal**  – Greyscale clean
* **elegant**  – Dark purple & Rose gold luxury

Data flow:
    Invoice Data → Common Invoice Template/Layout → Selected Theme → PDF
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    """Immutable colour palette for the PDF visual mode."""
    name: str
    label: str

    # Primary accent (header backgrounds, area borders, grand total box)
    navy: str
    # Secondary accent (gold highlights, area total borders, doc title underline)
    gold: str
    # Darker shade of gold (labels, headings)
    gold_dark: str
    # Main body text colour
    ink: str
    # Muted text (secondary labels, dates, footers)
    muted: str
    # Border colour for tables and dividers
    border: str
    # Row alternation / subtle backgrounds
    row_alt: str
    # Section header background (area headings, address box tops)
    section_bg: str
    # Address box background
    addr_bg: str
    # Grand total box background
    grand_bg: str
    # Grand total text colour
    grand_text: str
    # Words box background
    words_bg: str
    # Area total background
    area_total_bg: str
    # Table header text colour
    thead_text: str
    # Footer border
    footer_border: str
    # Footer text
    footer_text: str
    # Page background
    page_bg: str
    # "INVOICE" badge text colour
    badge_text: str
    # Customer name / area heading colour
    heading_text: str
    # Row text colour
    row_text: str
    # Accent red for area-total / grand-total digits (chosen to remain readable
    # on both the light area-total background and the dark grand-total box)
    red: str


# ---------------------------------------------------------------------------
# Built-in themes
# ---------------------------------------------------------------------------

COLOUR = Theme(
    name="colour",
    label="Colour / Premium",
    navy="#173560",
    gold="#C8A24B",
    gold_dark="#9C7B2E",
    ink="#223044",
    muted="#5A6B82",
    border="#D9E0EB",
    row_alt="#F7F9FC",
    section_bg="#EFF3FA",
    addr_bg="#FDFDFF",
    grand_bg="#173560",
    grand_text="#ffffff",
    words_bg="#FBFCFE",
    area_total_bg="#F4F7FC",
    thead_text="#ffffff",
    footer_border="#173560",
    footer_text="#5A6B82",
    page_bg="#ffffff",
    badge_text="#ffffff",
    heading_text="#173560",
    row_text="#223044",
    red="#E53935",
)

CLASSIC = Theme(
    name="classic",
    label="Classic / Professional",
    navy="#1A1A1A",
    gold="#333333",
    gold_dark="#222222",
    ink="#1A1A1A",
    muted="#666666",
    border="#CCCCCC",
    row_alt="#F5F5F5",
    section_bg="#EEEEEE",
    addr_bg="#FAFAFA",
    grand_bg="#1A1A1A",
    grand_text="#ffffff",
    words_bg="#FAFAFA",
    area_total_bg="#F0F0F0",
    thead_text="#ffffff",
    footer_border="#1A1A1A",
    footer_text="#666666",
    page_bg="#ffffff",
    badge_text="#ffffff",
    heading_text="#1A1A1A",
    row_text="#1A1A1A",
    red="#C62828",
)

MODERN = Theme(
    name="modern",
    label="Modern / Fresh",
    navy="#0D9488",
    gold="#F97316",
    gold_dark="#C2410C",
    ink="#1E293B",
    muted="#64748B",
    border="#CBD5E1",
    row_alt="#F0FDFA",
    section_bg="#CCFBF1",
    addr_bg="#F0FDFA",
    grand_bg="#0D9488",
    grand_text="#ffffff",
    words_bg="#F0FDFA",
    area_total_bg="#CCFBF1",
    thead_text="#ffffff",
    footer_border="#0D9488",
    footer_text="#64748B",
    page_bg="#ffffff",
    badge_text="#ffffff",
    heading_text="#0D9488",
    row_text="#1E293B",
    red="#E11D48",
)

MINIMAL = Theme(
    name="minimal",
    label="Minimal / Greyscale",
    navy="#374151",
    gold="#6B7280",
    gold_dark="#4B5563",
    ink="#111827",
    muted="#9CA3AF",
    border="#E5E7EB",
    row_alt="#F9FAFB",
    section_bg="#F3F4F6",
    addr_bg="#FFFFFF",
    grand_bg="#374151",
    grand_text="#ffffff",
    words_bg="#F9FAFB",
    area_total_bg="#F3F4F6",
    thead_text="#ffffff",
    footer_border="#D1D5DB",
    footer_text="#9CA3AF",
    page_bg="#ffffff",
    badge_text="#ffffff",
    heading_text="#374151",
    row_text="#111827",
    red="#DC2626",
)

ELEGANT = Theme(
    name="elegant",
    label="Elegant / Luxury",
    navy="#44337A",
    gold="#B7791F",
    gold_dark="#975A16",
    ink="#2D3748",
    muted="#718096",
    border="#E2E8F0",
    row_alt="#FAF5FF",
    section_bg="#E9D8FD",
    addr_bg="#FAF5FF",
    grand_bg="#44337A",
    grand_text="#ffffff",
    words_bg="#FAF5FF",
    area_total_bg="#E9D8FD",
    thead_text="#ffffff",
    footer_border="#44337A",
    footer_text="#718096",
    page_bg="#ffffff",
    badge_text="#ffffff",
    heading_text="#44337A",
    row_text="#2D3748",
    red="#A1243C",
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

THEMES = {
    t.name: t for t in [COLOUR, CLASSIC, MODERN, MINIMAL, ELEGANT]
}


def get_theme(name: str | None = None) -> Theme:
    """Return the theme by *name*, falling back to COLOUR."""
    if name and name in THEMES:
        return THEMES[name]
    return COLOUR

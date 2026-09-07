"""Automatic icon mapping for areas.

Maps area names (keywords) to relevant emoji icons.
When a new area is created, its name is matched against keywords
to assign a sensible default icon automatically.
"""
from __future__ import annotations

# Keyword -> icon mapping (checked in order, first match wins)
_KEYWORD_ICONS: list[tuple[str, str]] = [
    ("kitchen", "\U0001F373"),
    ("hall", "\U0001F6CB"),
    ("living", "\U0001F6CB"),
    ("bedroom", "\U0001F6CF"),
    ("master", "\U0001F6CF"),
    ("bath", "\U0001F6BF"),
    ("toilet", "\U0001F6BF"),
    ("dining", "\U0001F37D"),
    ("pooja", "\U0001F64F"),
    ("prayer", "\U0001F64F"),
    ("temple", "\U0001F64F"),
    ("dress", "\U0001F457"),
    ("wardrobe", "\U0001F457"),
    ("office", "\U0001F4BC"),
    ("shop", "\U0001F3EA"),
    ("store", "\U0001F4E6"),
    ("garage", "\U0001F697"),
    ("balcony", "\U0001F305"),
    ("terrace", "\u2600\uFE0F"),
    ("roof", "\u2600\uFE0F"),
    ("garden", "\U0001F333"),
    ("lobby", "\U0001F3E0"),
    ("porch", "\U0001F3E0"),
    ("entrance", "\U0001F6AA"),
    ("door", "\U0001F6AA"),
    ("window", "\U0001F4A1"),
    ("carpenter", "\U0001FA9A"),
    ("cabinet", "\U0001F5C4"),
    ("shelf", "\U0001F4DA"),
    ("other", "\U0001F527"),
]

# Default icon for unrecognized areas
DEFAULT_ICON = "\U0001F3E0"


def get_area_icon(area_name: str) -> str:
    """Return a relevant emoji icon for the given area name.

    Matches against keywords case-insensitively.
    Returns a house icon for unrecognized names.
    """
    name_lower = area_name.lower()
    for keyword, icon in _KEYWORD_ICONS:
        if keyword in name_lower:
            return icon
    return DEFAULT_ICON

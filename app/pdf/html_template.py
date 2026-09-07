"""Premium invoice HTML layout builder.

Builds the visual blocks (header, bill-to, item rows, totals, terms,
signature, footer) as self-contained HTML fragments styled with an
A4-printed professional furniture-contractor look.

Uses a single fixed Colour / Premium theme (navy & gold).

This module is deliberately Qt-free: it only assembles HTML/CSS strings.
The actual pagination (splitting content into discrete A4 pages) is done by
``app.pdf.paginate`` after measuring real rendered heights.

Everything shown is read from the database (BusinessProfile / Invoice /
Customer / Project / items). Nothing is hardcoded.
"""
from __future__ import annotations

import base64
import html
import io
from pathlib import Path

from app.pdf.theme import get_theme
from app.utils.calculations import amount_in_words


def _compute_area_totals_from_items(items):
    """Group item rows by area and return {area: total} for the PDF display."""
    from app.utils.calculations import compute_area_totals
    return compute_area_totals(items)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _esc(v):
    if v is None:
        return ""
    return html.escape(str(v), quote=True)


def _money(v) -> str:
    try:
        return f"{float(v or 0):,.2f}"
    except (TypeError, ValueError):
        return ""


def _money_inr(v, currency="₹") -> str:
    try:
        amt = f"{float(v or 0):,.2f}"
    except (TypeError, ValueError):
        return ""
    return f"{_esc(currency)} {amt}"


def _fmt_raw(v) -> str:
    """Format a qty/rate cell: preserve LS / text, else strip trailing .0."""
    if v is None or str(v).strip() == "":
        return ""
    s = str(v).strip()
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
        return f"{f:g}"
    except (TypeError, ValueError):
        return s


def _media_to_data_uri(path: str | None, upscale_min: int = 0, max_dim: int = 480) -> str:
    """Embed a media file as a data URI.

    Oversized images (e.g. huge logo PNGs) are downscaled and re-encoded
    before embedding, because a very large base64 ``data:`` URI can make
    WebEngine's ``printToPdf`` produce an empty (blank) PDF.
    """
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    ext = p.suffix.lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml", ".bmp": "image/bmp"}.get(ext, "image/png")
    try:
        data = p.read_bytes()
    except OSError:
        return ""
    # For raster formats, downscale very large images so the data URI stays small.
    if ext in (".png", ".jpg", ".jpeg", ".bmp"):
        try:
            from PIL import Image
            img = Image.open(p)
            img.load()
            w, h = img.size
            needs_resize = (max_dim and (w > max_dim or h > max_dim))
            if upscale_min and (w < upscale_min or h < upscale_min):
                target = min(upscale_min, max(w, h) * 4)
                factor = max(1.0, target / float(max(w, h)))
                nw = max(1, round(w * factor))
                nh = max(1, round(h * factor))
                img = img.resize((nw, nh), Image.LANCZOS)
            elif needs_resize:
                scale = max_dim / float(max(w, h))
                nw = max(1, round(w * scale))
                nh = max(1, round(h * scale))
                img = img.resize((nw, nh), Image.LANCZOS)
            data = _encode_pillow(img, ext)
        except Exception:  # noqa: BLE001, S110
            pass
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _encode_pillow(img, ext: str) -> bytes:
    buf = io.BytesIO()
    fmt = "JPEG" if ext in (".jpg", ".jpeg") else "PNG"
    if fmt == "JPEG":
        img = img.convert("RGB")
    else:
        img = img.convert("RGBA")
    img.save(buf, format=fmt)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Visual constants (defaults, overridden per-profile via build_css)
# ---------------------------------------------------------------------------
PAGE_W = 210
PAGE_H = 297
MARGIN = 15


def _get_profile_margins(profile=None) -> tuple[float, float, float, float]:
    """Return (top, bottom, left, right) margins in mm from profile or defaults."""
    if profile is None:
        return (MARGIN, MARGIN, MARGIN, MARGIN)
    return (
        float(getattr(profile, "pdf_margin_top", MARGIN) or MARGIN),
        float(getattr(profile, "pdf_margin_bottom", MARGIN) or MARGIN),
        float(getattr(profile, "pdf_margin_left", MARGIN) or MARGIN),
        float(getattr(profile, "pdf_margin_right", MARGIN) or MARGIN),
    )


def _get_paper_size(profile=None) -> tuple[float, float]:
    """Return (width_mm, height_mm) for the configured paper size."""
    size = "A4"
    if profile:
        size = getattr(profile, "pdf_paper_size", "A4") or "A4"
    sizes = {
        "A4": (210, 297),
        "A5": (148, 210),
        "LETTER": (216, 279),
    }
    return sizes.get(size.upper(), (210, 297))
COL_SN = 11
COL_SIZE = 28
COL_QTY = 13
COL_RATE = 24
COL_AMT = 31
COL_DESC_MIN = 70


# ---------------------------------------------------------------------------
# CSS generator (theme-aware)
# ---------------------------------------------------------------------------

_css_cache: dict[str, str] = {}


def build_css(profile=None) -> str:
    """Generate the complete CSS string using the selected theme.

    If the profile specifies a ``pdf_theme`` that is used as the base.
    Custom primary/secondary colours from the profile override the base
    theme's accents, letting each business brand their invoices.

    All ``__PLACEHOLDER__`` tokens are replaced with the theme's values,
    producing a self-contained stylesheet ready for embedding in the HTML.
    """
    # Build cache key from profile settings
    cache_key = (
        getattr(profile, "pdf_theme", "") if profile else "",
        getattr(profile, "pdf_primary_color", "") if profile else "",
        getattr(profile, "pdf_secondary_color", "") if profile else "",
    )
    if cache_key in _css_cache:
        return _css_cache[cache_key]
    # Start with the profile's chosen theme (or default COLOUR)
    theme_name = getattr(profile, "pdf_theme", "") if profile else ""
    theme = get_theme(theme_name)
    # Build an overridden theme if the profile specifies custom colours
    if profile:
        primary = getattr(profile, "pdf_primary_color", "") or ""
        secondary = getattr(profile, "pdf_secondary_color", "") or ""
        if primary or secondary:
            # Derive darker/lighter shades from the provided hex colours
            def _darken(hex_color: str, factor: float = 0.6) -> str:
                hex_color = hex_color.lstrip("#")
                if len(hex_color) != 6:
                    return hex_color
                r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"

            def _lighten(hex_color: str, factor: float = 1.6) -> str:
                hex_color = hex_color.lstrip("#")
                if len(hex_color) != 6:
                    return hex_color
                r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                return f"#{min(int(r*factor),255):02x}{min(int(g*factor),255):02x}{min(int(b*factor),255):02x}"

            navy = primary if primary else theme.navy
            gold = secondary if secondary else theme.gold
            # Recompute derived colours
            theme = theme.__class__(
                name=theme.name, label=theme.label,
                navy=navy, gold=gold,
                gold_dark=_darken(gold),
                ink=theme.ink, muted=theme.muted, border=theme.border,
                row_alt=theme.row_alt,
                section_bg=_lighten(navy, 1.8),
                addr_bg=theme.addr_bg,
                grand_bg=navy,
                grand_text="#ffffff",
                words_bg=theme.words_bg,
                area_total_bg=_lighten(navy, 1.7),
                thead_text="#ffffff",
                footer_border=navy,
                footer_text=theme.footer_text,
                page_bg=theme.page_bg,
                badge_text="#ffffff",
                heading_text=navy,
                row_text=theme.row_text,
                red=theme.red,
            )
    paper_w, paper_h = _get_paper_size(profile)
    paper_name = (getattr(profile, 'pdf_paper_size', 'A4') if profile else 'A4') or 'A4'
    css = """
@page { size: __PAPER__ portrait; margin: 0; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', 'Segoe UI Variable Text', Tahoma, Arial, sans-serif;
  color: __INK__; font-size: 10.5px; line-height: 1.32;
}
.page {
  width: __PW__mm; height: __PH__mm;
  padding: __MARGIN__mm;
  position: relative;
  display: block;
  overflow: hidden;
  page-break-inside: avoid;
  background: __PAGE_BG__;
}
.page:last-child { }

/* ---------- header ---------- */
.head { width: 100%; display: flex; align-items: stretch; }
.head-left { flex: 1 1 auto; display: flex; align-items: center; }
.head-logo { margin-right: 6mm; display: flex; align-items: center; }
.head-logo img { max-height: 20mm; min-height: 12mm; max-width: 45mm; width: auto; object-fit: contain; }
.head-biz .hb-name { font-size: 22px; font-weight: 800; color: __NAVY__; letter-spacing: .3px; }
.head-biz .hb-type { font-size: 9.5px; color: __GOLD_DARK__; font-weight: 700; letter-spacing: 1.6px; text-transform: uppercase; margin-top: 1px; }
.head-biz .hb-line { font-size: 9px; color: __MUTED__; margin-top: 1px; line-height: 1.45; }
.head-biz .hb-mob { color: __RED__; font-weight: 800; font-size: 10.5px; }
.head-right { text-align: right; margin-left: 6mm; }
.head-right .doc-title {
  font-size: 20px; font-weight: 800; color: __BADGE_TEXT__; background: __NAVY__;
  padding: 2.5mm 9mm; letter-spacing: 5px; display: inline-block;
  border-bottom: 1.6mm solid __GOLD__;
}
.meta { margin-top: 2.5mm; }
.meta .mr {
  display: flex; justify-content: flex-end; align-items: center;
  font-size: 9.5px; margin-top: 1mm;
}
.meta .mk { color: __MUTED__; margin-right: 3mm; }
.meta .mv { font-weight: 700; color: __INK__; }
.head-band { height: 1.1mm; background: linear-gradient(90deg, __NAVY__ 0% 70%, __GOLD__ 70% 100%); margin-top: 3.5mm; }

/* ---------- customer ---------- */
.addr-grid { display: flex; gap: 4mm; margin-top: 4.5mm; }
.addr-box {
  flex: 1 1 0; border: 0.3mm solid __BORDER__; border-top: 0.8mm solid __NAVY__;
  border-radius: 1.2mm; padding: 2.4mm 3mm; background: __ADDR_BG__;
}
.addr-label { font-size: 8px; font-weight: 800; color: __GOLD_DARK__; letter-spacing: 1.4px; text-transform: uppercase; margin-bottom: 1.6mm; }
.addr-name { font-size: 12px; font-weight: 800; color: __HEADING_TEXT__; margin-bottom: 1.2mm; }
.addr-line { font-size: 9px; color: __MUTED__; margin-top: 1px; line-height: 1.45; }
.cs-row { display: flex; align-items: baseline; justify-content: space-between; margin-top: 1.6mm; gap: 3mm; min-height: 0; }
.cs-item { font-size: 9px; color: __MUTED__; line-height: 1.4; }
.cs-right { text-align: right; }
.cs-key { font-weight: 800; color: __HEADING_TEXT__; margin-right: 1.5mm; }

/* ---------- column headings ---------- */
.thead {
  display: flex; align-items: stretch; width: 180mm;
  background: __NAVY__; color: __THEAD_TEXT__; border-radius: 1mm;
  border: 0.25mm solid __BORDER__;
  border-bottom: 0.9mm solid __GOLD__;
}
.thead > div { padding: 2.4mm 2mm; font-size: 11px; font-weight: 800; letter-spacing: .4px; color: __THEAD_TEXT__; }
.thead > div + div { border-left: 0.25mm solid __BORDER__; }
.t-ar { text-align: right; }

/* ---------- item rows ---------- */
.r { display: flex; align-items: stretch; width: 180mm; border-left: 0.25mm solid __BORDER__; border-right: 0.25mm solid __BORDER__; border-bottom: 0.25mm solid __BORDER__; }
.r > div { padding: 1.1mm 2.5mm; overflow: hidden; }
.r > div + div { border-left: 0.25mm solid __BORDER__; }
.r.alt { background: __ROW_ALT__; }
.c-sn   { width: __CSN__mm; min-width: __CSN__mm; font-weight: 800; color: __HEADING_TEXT__; text-align: center; }
.c-desc { width: __CDESC__mm; min-width: __CDESC__mm; flex: 1 1 auto; font-size: 10px; color: __ROW_TEXT__; }
.c-desc b { color: __ROW_TEXT__; font-weight: 600; }
.c-size { width: __CSIZE__mm; min-width: __CSIZE__mm; font-size: 10px; color: __MUTED__; white-space: nowrap; }
.c-qty  { width: __CQTY__mm; min-width: __CQTY__mm; font-size: 10px; text-align: center; color: __ROW_TEXT__; }
.c-rate { width: __CRATE__mm; min-width: __CRATE__mm; font-size: 10px; text-align: right; color: __ROW_TEXT__; }
.c-amt  { width: __CAMT__mm; min-width: __CAMT__mm; font-size: 10px; text-align: right; font-weight: 800; color: __ROW_TEXT__; white-space: nowrap; }

.area-row {
  display: flex; align-items: center; justify-content: center; text-align: center;
  margin-top: 2.2mm; margin-bottom: 0.5mm;
  background: __SECTION_BG__; border-left: 1.4mm solid __GOLD__; border-right: 1.4mm solid __GOLD__;
  width: 180mm; border-radius: 0 1mm 1mm 0;
}
.area-row .area-txt {
  font-size: 26.7px; font-weight: 800; color: __HEADING_TEXT__;
  letter-spacing: 1.6px; text-transform: uppercase;
  padding: 2mm 3mm;
}

.area-total {
  display: flex; align-items: center; justify-content: flex-end;
  margin-top: 1mm; margin-bottom: 1mm;
  background: __AREA_TOTAL_BG__; border-bottom: 0.5mm solid __GOLD__;
  width: 180mm; border-radius: 0 1mm 1mm 0;
  padding: 1.9mm 3mm;
}
.area-total .at-name { font-size: 13px; font-weight: 800; color: __HEADING_TEXT__; margin-right: auto; }
.area-total .at-val { font-size: 15px; font-weight: 800; color: __RED__; }

/* ---------- totals ---------- */
.totals { margin-top: 2.5mm; margin-left: auto; width: 120mm; }
.trow { display: flex; align-items: center; width: 120mm; padding: 1.2mm 2mm; }
.tlbl { flex: 1 1 auto; font-size: 16px; font-weight: 800; color: __MUTED__; text-align: right; }
.tval { width: 46mm; text-align: right; font-size: 18px; font-weight: 800; color: __ROW_TEXT__; }
.grand {
  margin-top: 1.5mm; background: __GRAND_BG__; border: 0.5mm solid __GOLD__; border-radius: 1.2mm;
  padding: 2mm 3mm; display: flex; align-items: center; width: 120mm;
}
.grand .glbl { font-size: 20px; font-weight: 800; color: __GOLD__; letter-spacing: 1.4px; flex: 1 1 auto; text-align: right; }
.grand .gval { width: 58mm; text-align: right; font-size: 18px; font-weight: 800; color: __RED__; white-space: nowrap; }

/* ---------- words ---------- */
.words {
  margin-top: 2mm; border: 0.3mm solid __BORDER__; border-left: 1mm solid __GOLD__;
  background: __WORDS_BG__; padding: 1.8mm 3mm; width: 100%;
}
.words .wk { font-size: 8.5px; font-weight: 800; color: __GOLD_DARK__; letter-spacing: 1.2px; text-transform: uppercase; }
.words .wv { font-size: 10.5px; font-weight: 700; color: __HEADING_TEXT__; margin-top: 0.8mm; }

/* ---------- terms ---------- */
.terms { margin-top: 2mm; width: 100%; }
.terms .tk { font-size: 8.5px; font-weight: 800; color: __GOLD_DARK__; letter-spacing: 1.2px; text-transform: uppercase; }
.terms .tv { font-size: 8.8px; color: __MUTED__; margin-top: 1mm; line-height: 1.35; white-space: pre-line; }

/* ---------- signature ---------- */
.sign-row { margin-top: 1.5mm; display: flex; justify-content: flex-end; }
.sign-box { text-align: center; }
.sign-line { width: 52mm; border-top: 0.4mm solid __INK__; margin-top: 4mm; padding-top: 1.3mm; font-size: 9.6px; font-weight: 700; color: __HEADING_TEXT__; }
.sign-tag { font-size: 8px; color: __MUTED__; letter-spacing: 1px; margin-top: 1mm; }

/* ---------- footer ---------- */
.foot {
  position: absolute; left: __MARGIN__mm; right: __MARGIN__mm; bottom: __MARGIN__mm;
  border-top: 0.4mm solid __FOOTER_BORDER__; padding-top: 1.6mm;
  display: flex; align-items: center;
}
.foot-left { flex: 1 1 auto; font-size: 8.2px; color: __FOOTER_TEXT__; line-height: 1.5; }
.foot-thanks { font-size: 8.6px; font-style: italic; color: __GOLD_DARK__; }
.foot-right { text-align: right; font-size: 8.2px; color: __FOOTER_TEXT__; }
.foot-right .pg { font-weight: 700; color: __HEADING_TEXT__; }

/* measurement harness */
#lin { width: 180mm; }
#lin > div { }
"""
    # Use profile margins/paper if available
    mt, mb, ml, mr = _get_profile_margins(profile)
    pw, ph = _get_paper_size(profile)
    margin_avg = (mt + mb + ml + mr) / 4.0
    result = (css
        .replace("__PAPER__", paper_name)
        .replace("__PW__", str(paper_w))
        .replace("__PH__", str(paper_h))
        .replace("__MARGIN__", str(margin_avg))
        .replace("__PAGE_W__", str(pw - ml - mr))
        .replace("__PAGE_H__", str(ph - mt - mb))
        .replace("__NAVY__", theme.navy)
        .replace("__GOLD__", theme.gold)
        .replace("__GOLD_DARK__", theme.gold_dark)
        .replace("__INK__", theme.ink)
        .replace("__MUTED__", theme.muted)
        .replace("__BORDER__", theme.border)
        .replace("__ROW_ALT__", theme.row_alt)
        .replace("__SECTION_BG__", theme.section_bg)
        .replace("__ADDR_BG__", theme.addr_bg)
        .replace("__GRAND_BG__", theme.grand_bg)
        .replace("__GRAND_TEXT__", theme.grand_text)
        .replace("__WORDS_BG__", theme.words_bg)
        .replace("__AREA_TOTAL_BG__", theme.area_total_bg)
        .replace("__THEAD_TEXT__", theme.thead_text)
        .replace("__FOOTER_BORDER__", theme.footer_border)
        .replace("__FOOTER_TEXT__", theme.footer_text)
        .replace("__PAGE_BG__", theme.page_bg)
        .replace("__BADGE_TEXT__", theme.badge_text)
        .replace("__HEADING_TEXT__", theme.heading_text)
        .replace("__ROW_TEXT__", theme.row_text)
        .replace("__RED__", theme.red)
        .replace("__CSN__", str(COL_SN))
        .replace("__CDESC__", str(COL_DESC_MIN))
        .replace("__CSIZE__", str(COL_SIZE))
        .replace("__CQTY__", str(COL_QTY))
        .replace("__CRATE__", str(COL_RATE))
        .replace("__CAMT__", str(COL_AMT))
    )
    _css_cache[cache_key] = result
    return result


# Backward-compatible CSS (fixed colour theme)
CSS = build_css()


# ---------------------------------------------------------------------------
# Layout object
# ---------------------------------------------------------------------------

class Layout:
    """Container of reusable HTML blocks for one invoice."""

    def __init__(self):
        self.header_html = ""
        self.billto_html = ""
        self.thead_html = ""
        self.items = []        # list of (block_id, html)
        self.final = []        # list of (block_id, html)
        self.billto_only = False
        self.currency = "₹"


def _item_row(blk_id, sn, desc, size, qty, rate, amount, alt):
    amt_txt = _money_inr(amount)
    return (
        f'<div class="r{" alt" if alt else ""}" id="{blk_id}">'
        f'<div class="c-sn">{sn}</div>'
        f'<div class="c-desc"><b>{_esc(desc)}</b></div>'
        f'<div class="c-size">{_esc(size)}</div>'
        f'<div class="c-qty">{_esc(qty)}</div>'
        f'<div class="c-rate">{_esc(rate)}</div>'
        f'<div class="c-amt">{amt_txt}</div>'
        f'</div>'
    )


def _area_row(blk_id, name):
    return f'<div class="area-row" id="{blk_id}"><span class="area-txt">{_esc(name)}</span></div>'


def _area_total_row(blk_id, name, total, currency):
    return (
        f'<div class="area-total" id="{blk_id}">'
        f'<span class="at-name">{_esc(name)} TOTAL</span>'
        f'<span class="at-val">{_money_inr(total, currency)}</span>'
        f'</div>'
    )


def build_layout(profile, invoice, customer, project, items) -> Layout:
    layout = Layout()

    # ---------------- header ----------------
    logo = _media_to_data_uri(profile.logo_path if profile else None, upscale_min=96)
    logo_html = f'<div class="head-logo"><img src="{logo}"/></div>' if logo else ""

    biz_name = profile.business_name if profile else "Business Name"
    biz_type = profile.business_type if profile else ""
    biz_lines = []
    if profile:
        if profile.mobile:
            biz_lines.append(f'Mobile: <span class="hb-mob">{_esc(profile.mobile)}</span>')
        if profile.email:
            biz_lines.append(f"Email: {profile.email}")
        if profile.gstin and profile.show_gst:
            biz_lines.append(f"GSTIN: {profile.gstin}")
        addr = profile.address or ""
        city_line = " ".join(x for x in [profile.city, profile.state, profile.pincode] if x)
        if city_line:
            addr = (addr + "<br/>" if addr else "") + _esc(city_line)
        if addr:
            biz_lines.insert(0, addr)
    biz_detail = "<br/>".join(biz_lines)

    inv_date = invoice.invoice_date.strftime("%d-%b-%Y") if invoice.invoice_date else "-"
    due_date = invoice.due_date.strftime("%d-%b-%Y") if invoice.due_date else "-"

    layout.header_html = (
        f'<div class="head" id="BLK-HEAD">'
        f'  <div class="head-left">{logo_html}<div class="head-biz">'
        f'    <div class="hb-name">{_esc(biz_name)}</div>'
        f'    {"<div class=\"hb-type\">" + _esc(biz_type) + "</div>" if biz_type else ""}'
        f'    <div class="hb-line">{biz_detail}&nbsp;</div>'
        f'  </div></div>'
        f'  <div class="head-right">'
        f'    <div class="doc-title">INVOICE</div>'
        f'    <div class="meta">'
        f'      <div class="mr"><span class="mk">Invoice No</span><span class="mv">{_esc(invoice.invoice_number)}</span></div>'
        f'      <div class="mr"><span class="mk">Date</span><span class="mv">{inv_date}</span></div>'
        f'      <div class="mr"><span class="mk">Due Date</span><span class="mv">{due_date}</span></div>'
        f'    </div>'
        f'  </div>'
        f'</div>'
        f'<div class="head-band"></div>'
    )

    # ---------------- bill to / project (single compact section) ----------------
    cust_name = customer.name if customer else "-"

    addr_parts = []
    site_display = ""
    contact = ""
    if customer:
        if customer.address:
            addr_parts.append(customer.address)
        addr_tail = " ".join(x for x in [customer.city, customer.state] if x)
        if addr_tail:
            addr_parts.append(addr_tail)
        if customer.mobile:
            contact = customer.mobile.strip()
    cust_addr = ", ".join(_esc(x) for x in addr_parts)

    if project and (project.name or "").strip():
        site_display = project.name.strip()
    elif project and (project.site_address or "").strip():
        site_display = project.site_address.strip()
    if not site_display and (invoice.site_address or "").strip():
        site_display = invoice.site_address.strip()

    cust_gst = f'<div class="addr-line">GSTIN: {_esc(customer.gstin)}</div>' \
        if (customer and customer.gstin and profile and profile.show_gst) else ""

    bits = ['<div class="addr-label">Bill To</div>',
            f'<div class="addr-name">{_esc(cust_name)}</div>']
    if cust_addr:
        bits.append(f'<div class="addr-line"><span class="cs-key">Address</span>{cust_addr}</div>')
    cs_items = []
    if contact:
        cs_items.append(f'<span class="cs-item"><span class="cs-key">Contact</span>{_esc(contact)}</span>')
    if site_display:
        cs_items.append(f'<span class="cs-item cs-right"><span class="cs-key">Site</span>{_esc(site_display)}</span>')
    if cs_items:
        bits.append(f'<div class="cs-row">{"".join(cs_items)}</div>{cust_gst}')
    else:
        bits.append(cust_gst)

    layout.billto_html = f'<div class="addr-box" id="BLK-GRID">{"".join(bits)}</div>'
    layout.billto_only = True

    # ---------------- column headings ----------------
    layout.thead_html = (
        f'<div class="thead">'
        f'<div class="c-sn">S.N.</div>'
        f'<div class="c-desc">DESCRIPTION</div>'
        f'<div class="c-size">SIZE</div>'
        f'<div class="c-qty t-ar">QTY</div>'
        f'<div class="c-rate t-ar">RATE ({_esc(profile.currency if profile else "₹")})</div>'
        f'<div class="c-amt t-ar">AMOUNT ({_esc(profile.currency if profile else "₹")})</div>'
        f'</div>'
    )

    # ---------------- items ----------------
    currency = _esc(profile.currency if profile else "₹")
    area_totals = _compute_area_totals_from_items(items)
    prev_area = None
    alt = False
    for sn, it in enumerate(items, start=1):
        area = (it.area or "OTHER").strip() or "OTHER"
        if area != prev_area:
            if prev_area is not None or sn == 1:
                layout.items.append((f"AR-{sn}", _area_row(f"AR-{sn}", area)))
            prev_area = area
        qty = _fmt_raw(it.qty_raw)
        rate = _fmt_raw(it.rate_raw)
        layout.items.append((
            f"IR-{sn}",
            _item_row(f"IR-{sn}", sn, it.description or "", it.size or "",
                      qty, rate, it.amount, alt),
        ))
        alt = not alt
        next_area = (items[sn].area or "OTHER").strip() or "OTHER" \
            if sn < len(items) else None
        if next_area != area or sn == len(items):
            layout.items.append((
                f"AT-{sn}",
                _area_total_row(f"AT-{sn}", area, area_totals.get(area, 0.0), currency),
            ))

    # ---------------- totals ----------------
    show_gst = bool(getattr(invoice, "gst_enabled", True))
    subt = float(invoice.subtotal or 0)
    disc = float(invoice.discount or 0)
    taxable = subt - disc
    rows = ""
    rows += (f'<div class="trow"><span class="tlbl">Subtotal</span>'
             f'<span class="tval">{_money_inr(invoice.subtotal, currency)}</span></div>')
    if disc > 0:
        rows += (f'<div class="trow"><span class="tlbl">Discount</span>'
                 f'<span class="tval">- {_money_inr(disc, currency)}</span></div>')
    rows += (f'<div class="trow"><span class="tlbl">Taxable Amount</span>'
             f'<span class="tval">{_money_inr(taxable, currency)}</span></div>')
    if show_gst and float(invoice.gst_amount or 0) > 0:
        rows += (f'<div class="trow"><span class="tlbl">GST ({_fmt_raw(invoice.gst_rate)}%)</span>'
                 f'<span class="tval">{_money_inr(invoice.gst_amount, currency)}</span></div>')

    totals_html = (
        f'<div class="totals" id="BLK-TOT">'
        f'{rows}'
        f'<div class="grand"><span class="glbl">GRAND TOTAL</span>'
        f'<span class="gval">{_money_inr(invoice.grand_total, currency)}</span></div>'
        f'</div>'
    )
    layout.final.append(("BLK-TOT", totals_html))

    # ---------------- words ----------------
    words = invoice.amount_in_words or amount_in_words(invoice.grand_total)
    layout.final.append(("BLK-WORDS",
        (f'<div class="words" id="BLK-WORDS"><div class="wk">Amount in Words</div>'
         f'<div class="wv">{_esc(words)}</div></div>')))

    # ---------------- terms ----------------
    terms = (profile.terms_conditions if profile else "") or ""
    if terms.strip():
        layout.final.append(("BLK-TERMS",
            (f'<div class="terms" id="BLK-TERMS"><div class="tk">Terms &amp; Conditions</div>'
             f'<div class="tv">{_esc(terms)}</div></div>')))

    # ---------------- signature ----------------
    sig_img = _media_to_data_uri(profile.signature_path if profile else None)
    sig_inner = (f'<img src="{sig_img}" style="max-width:48mm; max-height:18mm;"/>'
                 if sig_img else
                 '<div class="sign-line">Authorized Signatory</div>')
    layout.final.append(("BLK-SIG",
        (f'<div class="sign-row" id="BLK-SIG"><div class="sign-box">{sig_inner}'
         f'<div class="sign-tag">AUTHORIZED SIGNATURE</div></div></div>')))

    return layout


# ---------------------------------------------------------------------------
# Composer (given measured heights, build final paginated HTML)
# ---------------------------------------------------------------------------

def _foot_html(biz_lines, thanks, page_no, total_pages, currency_ignored=""):
    contact = " | ".join(_esc(x) for x in biz_lines)
    return (
        f'<div class="foot">'
        f'<div class="foot-left"><span class="foot-thanks">{_esc(thanks)}</span>'
        f'{"<br/>" + contact if contact else ""}</div>'
        f'<div class="foot-right"><span class="pg">Page {page_no} of {total_pages}</span></div>'
        f'</div>'
    )


def _footer_biz_lines(profile):
    lines = []
    if profile:
        if profile.mobile:
            lines.append(f"Mobile: {profile.mobile}")
        if profile.email:
            lines.append(profile.email)
        if profile.gstin and profile.show_gst:
            lines.append(f"GSTIN: {profile.gstin}")
    return lines

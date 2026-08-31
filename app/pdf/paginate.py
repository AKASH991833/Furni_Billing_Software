"""Pagination engine for the premium invoice PDF.

WebEngine/Chromium's support for automatic "repeat table header on each page"
and reliable ``@page`` margin boxes is limited and gives little control. So we
take a deterministic approach:

1. Build a *linear* HTML document containing every block (header, bill-to,
   item rows, area rows, totals, words, terms, signature) exactly once.
2. Render it in a hidden QWebEngineView and measure each block's real laid-out
   height (same engine + DPI that produces the PDF).
3. Pack the blocks into discrete ``.page`` boxes (each exactly A4), repeating
   the document header and column headings on every page, keeping rows whole,
   never separating an area heading from at least one following item, keeping
   the totals/words/terms/signature group together, and stamping a
   "Page N of M" footer on every page.

Because each physical page is a self-contained fixed-height ``.page`` div
paired with ``@page { size: A4 portrait; margin: 0 }``, the printed output has
guaranteed, pixel-consistent page breaks with no split rows.
"""
from __future__ import annotations

from app.pdf.html_template import CSS, Layout, _foot_html, _footer_biz_lines

# ---------------------------------------------------------------------------
# Layout constants (mm) — must match CSS in html_template.py
# ---------------------------------------------------------------------------
PAGE_W = 210.0
PAGE_H = 297.0
MARGIN = 15.0
# The .page box spans the full A4 page (210x297); the 15mm margin is applied
# as internal .page padding, so content lives inside a 180x267mm box.
TOP_PAD = MARGIN
BOTTOM_PAD = MARGIN
FOOT_H = 14.0
FOOT_GAP = 3.0
GAP = 1.0
THEAD_H = 9.5
# Conservative usable height so content never overflows the page box.
_USABLE = PAGE_H - TOP_PAD - BOTTOM_PAD - FOOT_H - FOOT_GAP - 6.0

_PX_PER_MM = 96.0 / 25.4


def _px_to_mm(px: float) -> float:
    return float(px) / _PX_PER_MM


def _measure(linear_html: str, view) -> dict:
    """Measure each block's height (in mm) using a provided QWebEngineView."""
    from PySide6.QtCore import QEventLoop, QTimer, QUrl

    result = {"done": False, "data": "[]"}
    view.setFixedSize(int(PAGE_W * _PX_PER_MM) + 200, 10000)
    view.setHtml(linear_html, QUrl("about:blank"))

    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)

    def _on_load(_ok):
        timer.start(20000)
        js = (
            "JSON.stringify(Array.from("
            "document.querySelectorAll('#lin > *')).map(function(e){"
            "return {id:e.id, h:Math.max(1,Math.ceil(e.getBoundingClientRect().height))};"
            "}))"
        )
        view.page().runJavaScript(js, lambda res: _finish(res))

    def _finish(res):
        result["data"] = res if isinstance(res, str) else "[]"
        result["done"] = True
        loop.quit()

    def _timeout():
        result["done"] = True
        loop.quit()

    timer.timeout.connect(_timeout)
    view.page().loadFinished.connect(_on_load)
    loop.exec()
    timer.stop()

    if not result["done"]:
        raise RuntimeError("Block measurement timed out.")
    try:
        import json
        arr = json.loads(result["data"])
    except Exception:  # noqa: BLE001
        arr = []
    return {d["id"]: _px_to_mm(d["h"]) for d in arr}


def _usable_cap(header_h: float, billto_h: float):
    """Vertical space for table content on first vs later pages."""
    first = _USABLE - header_h - GAP - billto_h - GAP - THEAD_H - GAP
    later = _USABLE - THEAD_H - GAP
    return first, later


def _render(profile, layout: Layout, heights: dict) -> str:
    header_h = heights.get("BLK-HEAD", 34.0)
    billto_h = heights.get("BLK-GRID", 24.0)
    cap_first, cap_later = _usable_cap(header_h, billto_h)

    item_html = {blk[0]: blk[1] for blk in layout.items}
    final_html = {blk[0]: blk[1] for blk in layout.final}
    final_ids = [blk[0] for blk in layout.final]

    # ---- pack item / area blocks into pages ----
    # Each page dict: {"items": [...ids], "first": bool, "used": float}
    pages = []
    cur = {"items": [], "first": True, "used": 0.0}
    pages.append(cur)

    def current_cap(page):
        return cap_first if page["first"] else cap_later

    def new_page():
        nonlocal cur
        new_first = False  # after first populated page, the rest are non-first
        nxt = {"items": [], "first": new_first, "used": 0.0}
        pages.append(nxt)
        cur = nxt

    item_ids = [blk[0] for blk in layout.items]
    for i, blk_id in enumerate(item_ids):
        bh = heights.get(blk_id, 6.5)
        need = bh + GAP
        cap = current_cap(cur)
        is_area = blk_id.startswith("AR-")
        is_atotal = blk_id.startswith("AT-")
        next_id = item_ids[i + 1] if i + 1 < len(item_ids) else None
        prev_id = item_ids[i - 1] if i > 0 else None

        force_break = (cur["used"] + need) > cap
        if is_area and next_id and not force_break:
            # keep the heading with at least its first item
            next_h = heights.get(next_id, 6.5)
            if (cur["used"] + need + GAP + next_h) > cap:
                force_break = True
        if is_atotal and prev_id and not force_break:
            # keep the area total with its last item (the row before it)
            prev_h = heights.get(prev_id, 6.5)
            if (cur["used"] + prev_h + GAP + need) > cap:
                force_break = True
        if force_break:
            new_page()
            cap = current_cap(cur)

        cur["items"].append(blk_id)
        cur["used"] += need

    # ---- place the invoice tail (totals/words/terms/signature) ----
    # Pack the tail blocks onto the last items page, using its remaining
    # vertical space; only spill a block onto a fresh page when it genuinely
    # does not fit. Avoid creating a near-empty page just for a small tail.
    # The authorized signature is glued to Terms & Conditions so it is never
    # stranded alone on its own page: if Terms fits on a page but the
    # signature does not, both move together to a shared tail page.
    final_ids = [blk[0] for blk in layout.final]
    for p in pages:
        p["final"] = []

    def place(bid, target):
        target["final"].append(bid)
        target["used"] += heights.get(bid, 8.0) + GAP

    sig_id = "BLK-SIG" if "BLK-SIG" in final_ids else None
    terms_id = "BLK-TERMS" if "BLK-TERMS" in final_ids else None

    remaining = current_cap(pages[-1]) - pages[-1]["used"]

    def start_final_page():
        nonlocal remaining
        new_page()
        cur["final"] = []
        remaining = current_cap(cur) - cur["used"]

    # Pack every tail block except the signature (which is glued to Terms).
    terms_page = None
    for bid in final_ids:
        need = heights.get(bid, 8.0) + GAP
        if bid == sig_id:
            continue
        if need <= remaining:
            place(bid, pages[-1])
            remaining -= need
        else:
            start_final_page()
            place(bid, cur)
            remaining -= need
        if bid == terms_id:
            terms_page = pages[-1]

    # Glue: put the signature on the same page as Terms.
    if sig_id:
        if terms_page is not None:
            if terms_page["used"] + heights.get(sig_id, 8.0) + GAP <= current_cap(terms_page):
                place(sig_id, terms_page)
                remaining -= heights.get(sig_id, 8.0) + GAP
            else:
                # Terms + signature share a fresh page so the signature is not
                # left alone. Pull Terms off its page and re-place them together.
                start_final_page()
                if terms_id in terms_page["final"]:
                    terms_page["final"].remove(terms_id)
                    terms_page["used"] -= heights.get(terms_id, 8.0) + GAP
                    place(terms_id, cur)
                place(sig_id, cur)
        else:
            # No Terms block: keep the signature with the last tail page.
            target = pages[-1]
            if target["used"] + heights.get(sig_id, 8.0) + GAP > current_cap(target):
                start_final_page()
                target = cur
            place(sig_id, target)

    import os
    if os.environ.get("PDF_DEBUG_PAGES"):
        print(f"[paginate] header={header_h:.1f} billto={billto_h:.1f} "
              f"cap_first={cap_first:.1f} cap_later={cap_later:.1f}")
        print(f"[paginate] tail_blocks={len(final_ids)} last_items={len(pages[-1]['items'])}")
        for i, p in enumerate(pages):
            print(f"[page {i}] first={p['first']} n_items={len(p['items'])} "
                  f"n_final={len(p['final'])} used={p['used']:.1f}")

    # ---- build final HTML ----
    total_pages = len(pages)
    biz_lines = _footer_biz_lines(profile)
    thank = "Thank you for your business."

    out = ["<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
           f"<style>{CSS}</style></head><body>"]
    page_no = 0
    for j, p in enumerate(pages):
        page_no += 1
        # Each .page is one physical page: force a break before every box
        # except the first, and after every box except the last.
        cls = "page-break-before: always;" if j > 0 else "page-break-after: always;"
        out.append(f'<div class="page" style="{cls}">')
        if p["first"]:
            out.append(layout.header_html)
            out.append(layout.billto_html)
        if p["items"]:
            out.append(layout.thead_html)
            for bid in p["items"]:
                out.append(item_html[bid])
        for bid in p["final"]:
            out.append(final_html[bid])
        out.append(_foot_html(biz_lines, thank, page_no, total_pages))
        out.append('</div>')
    out.append("</body></html>")
    return "\n".join(out)


def build_linear_html(layout: Layout) -> str:
    """Linear document used only to measure block heights."""
    parts = [layout.header_html]
    parts.append(f'<div id="BLK-THEAD" style="visibility:hidden;height:0;overflow:hidden;">'
                 f'{layout.thead_html}</div>')
    parts.append(layout.billto_html)
    for _bid, blk in layout.items:
        parts.append(blk)
    for _bid, blk in layout.final:
        parts.append(blk)
    return (
        f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        f"<style>{CSS}#lin {{ width:180mm; }}</style></head>"
        f"<body><div id='lin'>" + "".join(parts) + "</div></body></html>"
    )


def build_complete_html(profile, layout: Layout, view=None) -> str:
    """Measure blocks then compose the final paginated HTML.

    If ``view`` is provided it is reused (recommended for stability when the
    caller already owns a QWebEngineView); otherwise a fresh view is created.
    """
    if view is None:
        from PySide6.QtWebEngineWidgets import QWebEngineView
        view = QWebEngineView()
        own_view = True
    else:
        own_view = False
    try:
        linear = build_linear_html(layout)
        heights = _measure(linear, view)
    finally:
        if own_view:
            view.deleteLater()
    import os
    if os.environ.get("PDF_DEBUG_HEIGHTS"):
        print("HEIGHTS:", {k: round(v, 1) for k, v in heights.items()})
    return _render(profile, layout, heights)

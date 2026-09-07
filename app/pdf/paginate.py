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

from app.pdf.html_template import Layout, _foot_html, _footer_biz_lines, build_css

# ---------------------------------------------------------------------------
# Layout constants (mm) -- defaults, overridden per-profile
# ---------------------------------------------------------------------------
DEFAULT_PAGE_W = 210.0
DEFAULT_PAGE_H = 297.0
DEFAULT_MARGIN = 15.0
# Backward-compatible aliases for imports
PAGE_W = DEFAULT_PAGE_W
PAGE_H = DEFAULT_PAGE_H
MARGIN = DEFAULT_MARGIN
FOOT_H = 14.0
FOOT_GAP = 3.0
GAP = 1.0
THEAD_H = 9.5

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
            "var r=e.getBoundingClientRect();var s=getComputedStyle(e);"
            "var h=r.height"
            "+parseFloat(s.marginTop||0)+parseFloat(s.marginBottom||0);"
            "return {id:e.id, h:Math.max(0,h)};"
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
    conn = view.page().loadFinished.connect(_on_load)  # noqa: F841
    loop.exec()
    timer.stop()
    # Disconnect to avoid stale handler firing on the next setHtml() call.
    # PySide6's connect() returns a QMetaObject.Connection which has no
    # .disconnect() method, so disconnect via the signal/slot directly.
    try:
        view.page().loadFinished.disconnect(_on_load)
    except Exception:  # noqa: BLE001, S110
        pass

    if not result["done"]:
        raise RuntimeError("Block measurement timed out.")
    try:
        import json
        arr = json.loads(result["data"])
    except Exception:  # noqa: BLE001
        arr = []
    return {d["id"]: _px_to_mm(d["h"]) for d in arr}


def _usable_cap(header_h: float, billto_h: float, profile=None,
                thead_h: float | None = None, footer_h: float | None = None):
    """Vertical space (mm) for table content on first vs later pages.

    When real measured ``thead_h`` / ``footer_h`` are supplied, the capacity is
    derived from the ACTUAL footer height and the true page geometry, so that
    rows fill the page right down to the fixed footer boundary instead of
    leaving a large empty band above it.

    For backward compatibility, omitting them (or passing ``None``) keeps the
    historical fixed-estimate behaviour used by older callers/tests.
    """
    from app.pdf.html_template import _get_paper_size, _get_profile_margins
    mt, mb, ml, mr = _get_profile_margins(profile)
    _pw, ph = _get_paper_size(profile)

    if thead_h is None or footer_h is None:
        usable = ph - mt - mb - FOOT_H - FOOT_GAP - 6.0
        first = usable - header_h - GAP - billto_h - GAP - THEAD_H - GAP
        later = usable - THEAD_H - GAP
        return first, later

    # Footer's bottom edge sits `margin_avg` above the page bottom; its top
    # edge is the fixed lower boundary for in-flow content.
    margin_avg = (mt + mb + ml + mr) / 4.0
    gap = 3.0
    content_bottom = ph - margin_avg - float(footer_h) - gap
    content_top = float(mt)
    available = content_bottom - content_top
    first = available - float(header_h) - float(billto_h) - float(thead_h)
    later = available - float(thead_h)
    return first, later


def _render(profile, layout: Layout, heights: dict, css: str) -> str:
    header_h = heights.get("BLK-HEAD", 34.0)
    billto_h = heights.get("BLK-GRID", 24.0)
    thead_h = heights.get("BLK-THEAD", THEAD_H)
    footer_h = heights.get("BLK-FOOT", FOOT_H)
    cap_first, cap_later = _usable_cap(header_h, billto_h, profile, thead_h, footer_h)

    item_html = {blk[0]: blk[1] for blk in layout.items}
    final_html = {blk[0]: blk[1] for blk in layout.final}
    final_ids = [blk[0] for blk in layout.final]

    # ---- pack item / area blocks into pages ----
    pages = []
    cur = {"items": [], "first": True, "used": 0.0}
    pages.append(cur)

    def current_cap(page):
        return cap_first if page["first"] else cap_later

    def new_page():
        nonlocal cur
        nxt = {"items": [], "first": False, "used": 0.0}
        pages.append(nxt)
        cur = nxt

    item_ids = [blk[0] for blk in layout.items]
    for i, blk_id in enumerate(item_ids):
        bh = heights.get(blk_id, 6.5)
        need = bh
        cap = current_cap(cur)
        is_area = blk_id.startswith("AR-")
        is_atotal = blk_id.startswith("AT-")
        next_id = item_ids[i + 1] if i + 1 < len(item_ids) else None
        prev_id = item_ids[i - 1] if i > 0 else None

        force_break = (cur["used"] + need) > cap
        if is_area and next_id and not force_break:
            next_h = heights.get(next_id, 6.5)
            if (cur["used"] + need + next_h) > cap:
                force_break = True
        if is_atotal and prev_id and not force_break:
            prev_h = heights.get(prev_id, 6.5)
            # The area total must stay with its final row. If both cannot fit
            # on this page, undo the final row so it moves to the next page
            # TOGETHER with the area total (never separated).
            if (cur["used"] + need) > cap:
                cur["items"].pop()
                cur["used"] -= prev_h
                new_page()
                cap = current_cap(cur)
                cur["items"].append(prev_id)
                cur["used"] += prev_h
        if force_break:
            new_page()
            cap = current_cap(cur)

        cur["items"].append(blk_id)
        cur["used"] += need

    # ---- place the invoice tail (totals/words/terms/signature) ----
    final_ids = [blk[0] for blk in layout.final]
    for p in pages:
        p["final"] = []

    def place(bid, target):
        target["final"].append(bid)
        target["used"] += heights.get(bid, 8.0)

    sig_id = "BLK-SIG" if "BLK-SIG" in final_ids else None
    terms_id = "BLK-TERMS" if "BLK-TERMS" in final_ids else None

    remaining = current_cap(pages[-1]) - pages[-1]["used"]

    def start_final_page():
        nonlocal remaining
        new_page()
        cur["final"] = []
        remaining = current_cap(cur) - cur["used"]

    terms_page = None
    for bid in final_ids:
        need = heights.get(bid, 8.0)
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

    if sig_id:
        if terms_page is not None:
            if terms_page["used"] + heights.get(sig_id, 8.0) <= current_cap(terms_page):
                place(sig_id, terms_page)
                remaining -= heights.get(sig_id, 8.0)
            else:
                start_final_page()
                if terms_id in terms_page["final"]:
                    terms_page["final"].remove(terms_id)
                    terms_page["used"] -= heights.get(terms_id, 8.0)
                    place(terms_id, cur)
                place(sig_id, cur)
        else:
            target = pages[-1]
            if target["used"] + heights.get(sig_id, 8.0) > current_cap(target):
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

    out = [("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            f"<style>{css}</style></head><body>")]
    for j, p in enumerate(pages):
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
        out.append(_foot_html(biz_lines, thank, j + 1, total_pages))
        out.append('</div>')
    out.append("</body></html>")
    return "\n".join(out)


def build_linear_html(layout: Layout, css: str, profile=None) -> str:
    """Linear document used only to measure block heights.

    The document header, the table-heading row and the footer are rendered
    in-flow (the footer is forced static) so that their REAL laid-out heights
    are measured and can be used to compute dynamic page capacities.
    """
    biz_lines = _footer_biz_lines(profile)
    parts = [layout.header_html]
    parts.append(f'<div id="BLK-THEAD">{layout.thead_html}</div>')
    parts.append(f'<div id="BLK-FOOT">{_foot_html(biz_lines, "T", 1, 1)}</div>')
    parts.append(layout.billto_html)
    for _bid, blk in layout.items:
        parts.append(blk)
    for _bid, blk in layout.final:
        parts.append(blk)
    return (
        f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        f"<style>{css}#lin {{ width:180mm; }} "
        f"#lin .foot {{ position: static !important; }}"
        f"</style></head>"
        f"<body><div id='lin'>" + "".join(parts) + "</div></body></html>"
    )


def build_complete_html(profile, layout: Layout, view=None) -> str:
    """Measure blocks then compose the final paginated HTML.

    If ``view`` is provided it is reused (recommended for stability when the
    caller already owns a QWebEngineView); otherwise a fresh view is created.
    """
    css = build_css(profile)
    if view is None:
        from PySide6.QtWebEngineWidgets import QWebEngineView
        view = QWebEngineView()
        own_view = True
    else:
        own_view = False
    try:
        linear = build_linear_html(layout, css, profile)
        heights = _measure(linear, view)
    finally:
        if own_view:
            view.deleteLater()
    import os
    if os.environ.get("PDF_DEBUG_HEIGHTS"):
        print("HEIGHTS:", {k: round(v, 1) for k, v in heights.items()})
    return _render(profile, layout, heights, css)

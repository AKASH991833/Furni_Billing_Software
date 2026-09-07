"""PDF generation, preview, save and print service.

Uses Qt WebEngine (bundled with PySide6) to render the professional
HTML/CSS template to a true A4 portrait PDF locally — no external browser
or separate PDF binary is needed, keeping the standalone installer
self-contained.

The invoice is rendered with a single fixed Colour / Premium theme.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QPageLayout, QPageSize
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.pdf.html_template import build_layout
from app.pdf.paginate import build_complete_html
from app.services import business_service, invoice_service


def _showGenerating(parent) -> None:
    """Show a non-blocking 'Generating PDF…' status label in the parent widget.

    Because ``_write_pdf_sync`` runs a nested ``QEventLoop``, the label
    repaints while the PDF is being generated, giving the user visual
    feedback that something is happening.
    """
    if parent is None:
        return
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel
    lbl = QLabel("Generating PDF…", parent)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(
        "QLabel { background: rgba(37, 99, 235, 0.9); color: white;"
        " font-weight: 600; font-size: 14px; padding: 12px;"
        " border-radius: 8px; }"
    )
    lbl.setFixedSize(220, 44)
    # Position at bottom-right of parent
    pw = parent.width()
    ph = parent.height()
    lbl.move(pw - 240, ph - 60)
    lbl.show()
    lbl.repaint()  # Force immediate repaint so label appears before blocking
    # Auto-remove after 5 seconds as a safety net
    from PySide6.QtCore import QTimer
    QTimer.singleShot(5000, lbl.deleteLater)


def build_invoice_html(invoice_id: int) -> str:
    invoice = invoice_service.get_invoice(invoice_id)
    if invoice is None:
        raise ValueError("Invoice not found.")
    profile = business_service.get_profile()
    layout = build_layout(profile, invoice, invoice.customer, invoice.project, invoice.items)
    return build_complete_html(profile, layout)


# Reusable QWebEngineView singleton — avoids expensive
# Chromium initialization on every PDF generation.
_pdf_view: QWebEngineView | None = None


def _get_pdf_view() -> QWebEngineView:
    """Return a reusable QWebEngineView, creating it on first call."""
    global _pdf_view
    if _pdf_view is None:
        _pdf_view = QWebEngineView()
        _pdf_view.setFixedSize(794, 1123)
        # Pre-configure for faster rendering
        _pdf_view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        _pdf_view.settings().setAttribute(QWebEngineSettings.PluginsEnabled, False)
        _pdf_view.settings().setAttribute(QWebEngineSettings.AutoLoadImages, False)
    return _pdf_view


def _write_pdf_sync(invoice_id: int, destination: Path) -> None:
    """Render a PDF synchronously using a nested event loop."""

    invoice = invoice_service.get_invoice(invoice_id)
    if invoice is None:
        raise ValueError("Invoice not found.")
    profile = business_service.get_profile()
    layout = build_layout(profile, invoice, invoice.customer,
                          invoice.project, invoice.items)

    view = _get_pdf_view()
    html = build_complete_html(profile, layout, view=view)
    _print_html_to_file(view, html, destination)


def _print_html_to_file(view: QWebEngineView, html: str, destination: Path) -> None:
    """Load ``html`` into ``view`` and print it to ``destination`` as A4."""
    from PySide6.QtCore import QEventLoop, QMarginsF, QTimer, QUrl
    from PySide6.QtGui import QPageRanges, QPageSize

    layout = QPageLayout(
        QPageSize(QPageSize.A4),
        QPageLayout.Portrait,
        QMarginsF(0, 0, 0, 0),
        QPageLayout.Millimeter,
    )

    loop = QEventLoop()
    result = {"ok": False, "data": None, "error": None}

    watchdog = QTimer()
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(lambda: result.update(error="PDF generation timed out") or loop.quit())

    def _cb(data):
        watchdog.stop()
        if data is not None and len(data) > 0:
            result["ok"] = True
            result["data"] = bytes(data)
        else:
            result["error"] = "PDF generation produced empty output."
        loop.quit()

    def _generate():
        watchdog.start(30000)
        try:
            view.page().printToPdf(_cb, layout, QPageRanges())
        except Exception as e:  # noqa: BLE001
            result["error"] = e
            loop.quit()

    view.page().loadFinished.connect(lambda _o: _generate())
    view.setHtml(html, QUrl("about:blank"))

    loop.exec()
    watchdog.stop()

    if result.get("ok") and result["data"]:
        Path(destination).write_bytes(result["data"])
    else:
        raise RuntimeError(result["error"] or "PDF generation failed to produce output.")


def save_pdf(parent, invoice_id: int) -> Path | None:
    """Save PDF to user-chosen path."""
    invoice = invoice_service.get_invoice(invoice_id)
    if invoice is None:
        return None
    default_name = f"{(invoice.invoice_number or 'invoice')}.pdf"
    path, _ = QFileDialog.getSaveFileName(
        parent, "Save Invoice PDF", str(Path.home() / default_name),
        "PDF Files (*.pdf)")
    if not path:
        return None
    if not str(path).lower().endswith(".pdf"):
        path += ".pdf"
    try:
        _showGenerating(parent)
        _write_pdf_sync(invoice_id, Path(path))
        return Path(path)
    except Exception as e:  # noqa: BLE001
        QMessageBox.critical(parent, "Save failed", f"Could not save PDF:\n{e}")
        return None


class PdfPreviewDialog(QDialog):
    """Preview and print the generated invoice.

    The preview renders the actual invoice HTML directly in the embedded
    QWebEngineView rather than loading a generated .pdf file. Loading a PDF
    into QWebEngineView relies on its flaky built-in viewer (which frequently
    shows a black screen), whereas HTML renders reliably and is exactly what
    gets sent to the printer / PDF serializer.
    """

    def __init__(self, invoice_id: int, parent=None):
        super().__init__(parent)
        self.invoice_id = invoice_id
        self.setWindowTitle("Invoice PDF Preview")
        self.resize(860, 920)
        self.setMinimumSize(600, 600)
        self._view_ready = False
        self._html = None
        self._build()

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)

        # --- Scrollable preview area ---
        # Wrap QWebEngineView in QScrollArea so multi-page invoices scroll.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        # Container widget inside scroll area
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(0)

        # Preview view (renders HTML, not PDF)
        self.view = QWebEngineView()
        self.view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.view.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        # Let WebEngine handle its own internal scrolling
        self.view.setMinimumHeight(800)
        self._container_layout.addWidget(self.view)

        scroll.setWidget(self._container)
        v.addWidget(scroll, 1)

        # --- Action buttons ---
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        btn_preview = QPushButton("Regenerate PDF")
        btn_preview.clicked.connect(self._load_preview)
        btn_save = QPushButton("Save PDF...")
        btn_save.clicked.connect(self._save)
        btn_print = QPushButton("Print...")
        btn_print.setObjectName("primaryButton")
        btn_print.clicked.connect(self._print)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        buttons.addWidget(btn_preview)
        buttons.addWidget(btn_save)
        buttons.addWidget(btn_print)
        buttons.addWidget(btn_close)
        v.addLayout(buttons)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._view_ready:
            self._view_ready = True
            self._load_preview()

    def _build_html(self) -> str:
        """Build the paginated invoice HTML, decorated for paged preview."""
        from app.pdf.paginate import build_complete_html
        invoice = invoice_service.get_invoice(self.invoice_id)
        if invoice is None:
            raise ValueError("Invoice not found.")
        profile = business_service.get_profile()
        layout = build_layout(profile, invoice, invoice.customer,
                              invoice.project, invoice.items)
        html = build_complete_html(profile, layout, view=self.view)
        return self._decorate_preview(html)

    @staticmethod
    def _decorate_preview(html: str) -> str:
        """Inject preview-only CSS/JS so each A4 page shows as a distinct sheet.

        The paginated HTML emits one ``.page`` div per physical page back to
        back. On a plain white background they merge into a single long strip.
        Here we show each page as a separate card: a light workspace behind it,
        a visible gap, a drop shadow, and a "Page N of M" label above each page.
        These decorations only affect the on-screen preview — the saved PDF and
        print output are generated separately and are unaffected.
        """
        decoration = """
        <style>
          html, body { background: #e3e6ea !important; }
          .page {
            margin: 18px auto 26px auto !important;
            box-shadow: 0 4px 18px rgba(0, 0, 0, 0.30) !important;
          }
          .preview-pagenum {
            width: 178mm; margin: 12px auto 0 auto; text-align: center;
            font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px;
            font-weight: 600; color: #4a5568; letter-spacing: .6px;
          }
        </style>
        <script>
          window.addEventListener('load', function () {
            var pages = Array.prototype.slice.call(document.querySelectorAll('.page'));
            for (var i = 0; i < pages.length; i++) {
              var label = document.createElement('div');
              label.className = 'preview-pagenum';
              label.textContent = 'Page ' + (i + 1) + ' of ' + pages.length;
              pages[i].parentNode.insertBefore(label, pages[i]);
            }
          });
        </script>
        """
        return html.replace("</body>", decoration + "</body>")

    def _load_preview(self):
        """Render the invoice HTML directly in the preview view."""
        try:
            self._html = self._build_html()
            self.view.setHtml(self._html, QUrl("about:blank"))
            # After page loads, resize the view to fit all content
            self.view.page().loadFinished.connect(self._on_load_finished)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Preview failed", str(e))

    def _on_load_finished(self, ok: bool):
        """Resize the WebEngineView to fit the full HTML content height."""
        if not ok:
            return
        # Use JavaScript to get the full document height and resize the view
        js = "document.documentElement.scrollHeight"
        self.view.page().runJavaScript(js, self._resize_to_content)

    def _resize_to_content(self, height):
        """Set the view height to match the rendered content."""
        if height and isinstance(height, (int, float)) and height > 100:
            # Add small padding to avoid clipping
            self.view.setMinimumHeight(int(height) + 20)
            self.view.setFixedHeight(int(height) + 20)

    def _save(self):
        from PySide6.QtWidgets import QFileDialog
        invoice = invoice_service.get_invoice(self.invoice_id)
        default = f"{(invoice.invoice_number or 'invoice')}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Invoice PDF", str(Path.home() / default), "PDF Files (*.pdf)")
        if not path:
            return
        if not str(path).lower().endswith(".pdf"):
            path += ".pdf"
        try:
            _showGenerating(self)
            _write_pdf_sync(self.invoice_id, Path(path))
            QMessageBox.information(self, "Saved", f"PDF saved to:\n{path}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", str(e))

    def _print(self):
        try:
            from PySide6.QtGui import QPageLayout
            from PySide6.QtPrintSupport import QPrintDialog, QPrinter
            printer = QPrinter(QPrinter.HighResolution)
            printer.setPageSize(QPageSize(QPageSize.A4))
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)
            dlg = QPrintDialog(printer, self)
            if dlg.exec() == QPrintDialog.Accepted:
                self.view.page().print(printer, lambda b: None)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Print failed", str(e))

"""PDF generation, preview, save and print service.

Uses Qt WebEngine (bundled with PySide6) to render the professional
HTML/CSS template to a true A4 portrait PDF locally — no external browser
or separate PDF binary is needed, keeping the standalone installer
self-contained.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from PySide6.QtGui import QPageLayout, QPageSize

from app.pdf.html_template import build_layout
from app.pdf.paginate import build_complete_html
from app.services import business_service, customer_service, invoice_service
from app.utils.paths import data_dir


def build_invoice_html(invoice_id: int) -> str:
    invoice = invoice_service.get_invoice(invoice_id)
    if invoice is None:
        raise ValueError("Invoice not found.")
    profile = business_service.get_profile()
    layout = build_layout(profile, invoice, invoice.customer, invoice.project, invoice.items)
    return build_complete_html(profile, layout)


def _write_pdf_sync(invoice_id: int, destination: Path) -> None:
    """Render a PDF synchronously using a nested event loop.

    printToPdf is asynchronous, but calling it inside the running QApp event
    loop via QEventLoop yields until completion, so callers get a ready file.
    A true A4 portrait layout is applied explicitly (independent of printer/UI).

    A single QWebEngineView is reused for both block measurement and the final
    print — creating many WebEngine views in one process is unstable in some
    environments, so we avoid it here.
    """
    from PySide6.QtCore import QEventLoop, QUrl
    from PySide6.QtGui import QPageLayout, QPageRanges, QPageSize

    invoice = invoice_service.get_invoice(invoice_id)
    if invoice is None:
        raise ValueError("Invoice not found.")
    profile = business_service.get_profile()
    layout = build_layout(profile, invoice, invoice.customer,
                          invoice.project, invoice.items)

    view = QWebEngineView()
    view.setFixedSize(794, 1123)
    try:
        # Measure + compose the final paginated HTML on the shared view.
        html = build_complete_html(profile, layout, view=view)
        _print_html_to_file(view, html, destination)
    finally:
        view.deleteLater()


def _print_html_to_file(view: QWebEngineView, html: str, destination: Path) -> None:
    """Load ``html`` into ``view`` and print it to ``destination`` as A4."""
    from PySide6.QtCore import QEventLoop, QMarginsF, QTimer, QUrl
    from PySide6.QtGui import QPageLayout, QPageRanges, QPageSize

    layout = QPageLayout(
        QPageSize(QPageSize.A4),
        QPageLayout.Portrait,
        QMarginsF(0, 0, 0, 0),
        QPageLayout.Millimeter,
    )

    loop = QEventLoop()
    result = {"ok": False, "data": None, "error": None}

    # Overall watchdog so the nested loop can never hang the GUI thread.
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
    invoice = invoice_service.get_invoice(invoice_id)
    default_name = f"{(invoice.invoice_number or 'invoice')}.pdf"
    path, _ = QFileDialog.getSaveFileName(
        parent, "Save Invoice PDF", str(Path.home() / default_name),
        "PDF Files (*.pdf)")
    if not path:
        return None
    if not str(path).lower().endswith(".pdf"):
        path += ".pdf"
    try:
        _write_pdf_sync(invoice_id, Path(path))
        return Path(path)
    except Exception as e:  # noqa: BLE001
        QMessageBox.critical(parent, "Save failed", f"Could not save PDF:\n{e}")
        return None


class PdfPreviewDialog(QDialog):
    """Preview and print the generated PDF."""

    def __init__(self, invoice_id: int, parent=None):
        super().__init__(parent)
        self.invoice_id = invoice_id
        self.setWindowTitle("Invoice PDF Preview")
        self.resize(860, 920)
        self.setMinimumSize(600, 600)
        self._view_ready = False
        self._build()

    def _build(self):
        v = QVBoxLayout(self)
        self.view = QWebEngineView()
        self.view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, False)
        self.view.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        v.addWidget(self.view, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        btn_preview = QPushButton("Regenerate PDF")
        btn_preview.clicked.connect(self._load_pdf)
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
            self._load_pdf()

    def _pdf_path(self) -> Path:
        return data_dir() / "preview.pdf"

    def _load_pdf(self):
        try:
            _write_pdf_sync(self.invoice_id, self._pdf_path())
            self.view.load(QUrl.fromLocalFile(str(self._pdf_path())))
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Preview failed", str(e))

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
            _write_pdf_sync(self.invoice_id, Path(path))
            QMessageBox.information(self, "Saved", f"PDF saved to:\n{path}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", str(e))

    def _print(self):
        try:
            from PySide6.QtPrintSupport import QPrintDialog, QPrinter
            printer = QPrinter(QPrinter.HighResolution)
            printer.setPageSize(QPageSize(QPageSize.A4))
            printer.setPageOrientation(QPrinter.Portrait)
            dlg = QPrintDialog(printer, self)
            if dlg.exec() == QPrintDialog.Accepted:
                self.view.page().print(printer, lambda b: None)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Print failed", str(e))

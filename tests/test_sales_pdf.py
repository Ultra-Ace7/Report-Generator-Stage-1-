from pathlib import Path
from io import BytesIO
from decimal import Decimal
from docx import Document
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from core.exceptions import ReportError
from support import SAMPLES, build_readers
from core.report_service import ReportService, DEFAULT_TEMPLATE
from core.schemas import DateRange
from sources.pdf_reader import PdfInputReader


def test_sales_pdf_orders_and_docx(tmp_path):
    before = DEFAULT_TEMPLATE.read_bytes()
    data = PdfInputReader(SAMPLES/'sales_orders.pdf').read()
    assert len(data.orders) == 5
    assert str(data.orders[0].order_date) == '2026-10-03'
    assert sum(order.revenue for order in data.orders) == Decimal('7390.00')
    result = ReportService().generate('sales_summary', DateRange(start='2026-10-01',end='2026-10-31'),build_readers(metrics_file=SAMPLES/'sales_orders.pdf'),tmp_path/'out.docx')
    doc = Document(result.path)
    text = ' '.join(cell.text for table in doc.tables for row in table.rows for cell in row.cells)
    assert 'AUD 7,390.00' in text and 'AUD 1,478.00' in text
    assert len(doc.inline_shapes) == 1
    assert DEFAULT_TEMPLATE.read_bytes() == before


def test_sales_pdf_upload_ui(monkeypatch):
    pdf = BytesIO((SAMPLES/'sales_orders.pdf').read_bytes()); pdf.name='orders.pdf'
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:[pdf])
    monkeypatch.setattr('renderer.pdf_exporter.export_pdf',lambda data:b'%PDF-test')
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'),default_timeout=20).run()
    app.run()
    app.button(key='generate').click().run()
    assert not app.exception and app.success
    assert 'AUD 7,390.00' in app.session_state['generated_report']['summary']


def test_targets_pdf_preserved():
    data=PdfInputReader(SAMPLES/'monthly_metrics.pdf').read()
    assert len(data.monthly_targets)==2 and not data.orders

from pathlib import Path
"""Header compatibility without changing validated business facts."""
import csv
from io import BytesIO
from zipfile import ZipFile

from docx import Document
import httpx
from openpyxl import Workbook
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from core.exceptions import ReportError
from support import SAMPLES, build_readers
from core.report_service import DEFAULT_TEMPLATE, ReportService
from core.schemas import DateRange
from sources.api_reader import ApiTaskReader
from sources.csv_excel import COLUMNS, CsvExcelReader, normalize_rows
from sources.sales_fields import FIELD_ALIASES

ROW = ['001', '2026-10-01', 'Example', 'Support', '10.20', 'AUD']
ALIASES = ['Transaction ID', 'Date', 'Client Name', 'Product', 'Sales Amount', 'Currency Code']


@pytest.mark.parametrize('headers', [COLUMNS, [s.upper() for s in COLUMNS],
    [' Order-ID ', 'ORDER DATE', 'Customer_Name', 'Service-Type', 'TOTAL_AMOUNT', 'Currency-Code'], ALIASES])
def test_header_variants(headers):
    assert normalize_rows([headers, ROW]) == normalize_rows([COLUMNS, ROW])


@pytest.mark.parametrize('field,alias', [(field, alias) for field, aliases in FIELD_ALIASES.items() for alias in aliases])
def test_every_documented_alias(field, alias):
    headers = list(COLUMNS)
    headers[headers.index(field)] = alias
    assert normalize_rows([headers, ROW]) == normalize_rows([COLUMNS, ROW])


def test_extra_columns_and_reordering():
    assert normalize_rows([['Notes'] + list(reversed(ALIASES)), ['Ignore'] + list(reversed(ROW))]) == normalize_rows([COLUMNS, ROW])


@pytest.mark.parametrize('headers,row,message', [
    (COLUMNS[:-2], ROW[:-2], 'Missing required sales fields: revenue, currency'),
    (list(COLUMNS) + ['Total Amount'], ROW + ['10.20'], "Multiple columns map to 'revenue': revenue, Total Amount"),
    (ALIASES[:-2] + ['Total Amount', 'Currency', 'Tax Amount'], ROW + ['1.00'], 'Ambiguous revenue'),
    (ALIASES[:-2] + ['Amount', 'Currency', 'refund_amount'], ROW + ['1.00'], 'Ambiguous revenue'),
    (ALIASES[:-2] + ['Total Amount', 'Currency', 'Discount-Rate'], ROW + ['0.1'], 'Ambiguous revenue'),
])
def test_mapping_errors(headers, row, message):
    with pytest.raises(ReportError, match=message):
        normalize_rows([headers, row])


@pytest.mark.parametrize('index,value,field', [(1, '2026-02-30', 'order_date'), (1, '01/10/2026', 'order_date'),
    (4, 'ten', 'revenue'), (4, '-1', 'revenue'), (4, '0.001', 'revenue'), (5, 'USD', 'currency')])
def test_invalid_values_retain_row_and_field(index, value, field):
    row = list(ROW)
    row[index] = value
    with pytest.raises(ReportError, match='Sales row 2.*' + field):
        normalize_rows([ALIASES, row])


@pytest.mark.parametrize('suffix', ['csv', 'xlsx'])
def test_alias_input_three_sources_final_word(tmp_path, suffix):
    path = tmp_path / ('sales.' + suffix)
    if suffix == 'csv':
        with path.open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerows([ALIASES, ROW])
    else:
        book = Workbook()
        book.active.title = 'Custom First'
        book.active.append(ALIASES)
        book.active.append(ROW)
        book.save(path)
        book.close()
    reader = CsvExcelReader(path, sheet_name=None)
    assert reader.read() == normalize_rows([COLUMNS, ROW])
    template = DEFAULT_TEMPLATE.read_bytes()
    tasks = [{'userId': 1, 'id': 1, 'title': 'Task', 'completed': True}]
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=tasks))) as client:
        readers = [reader] + build_readers(metrics_file=SAMPLES / 'monthly_metrics.pdf') + [ApiTaskReader(client)]
        result = ReportService().generate('sales_summary', DateRange(start='2026-10-01', end='2026-10-31'), readers, tmp_path / 'report.docx')
    doc = Document(result.path)
    metrics = {row.cells[0].text: row.cells[1].text for row in doc.tables[0].rows[1:]}
    assert metrics['Recorded revenue'] == 'AUD 10.20'
    assert metrics['Sales target'] == 'AUD 8,000.00'
    assert doc.tables[1].rows[1].cells[0].text == '001'
    assert doc.tables[-1].rows[1].cells[1].text == '1'
    assert len(doc.inline_shapes) == 1
    assert DEFAULT_TEMPLATE.read_bytes() == template
    with ZipFile(BytesIO(template)) as original, ZipFile(result.path) as output:
        for part in ('word/styles.xml', 'word/header1.xml', 'word/footer1.xml', 'word/media/image1.png'):
            assert output.read(part) == original.read(part)


def test_pdf_only_sales_ui_requires_sales(monkeypatch):
    pdf = BytesIO((SAMPLES / 'monthly_metrics.pdf').read_bytes())
    pdf.name = 'metrics.pdf'
    monkeypatch.setattr(st, 'file_uploader', lambda *args, **kwargs: [pdf])
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=20).run()
    app.run()
    app.button(key='generate').click().run()
    assert not app.exception
    assert 'Sales Summary requires sales data' in app.error[0].value
    assert not app.get('download_button')

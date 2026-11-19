from pathlib import Path
"""Controlled sales HTTP responses through the existing report pipeline."""
import json
from io import BytesIO
from docx import Document
import httpx
import pytest
from streamlit.testing.v1 import AppTest
from cli import main
from core.exceptions import ReportError
from support import SAMPLES, build_readers
from core.report_service import DEFAULT_TEMPLATE, ReportService
from core.schemas import DateRange
from sources.sales_api import ApiSalesReader

URL = 'https://example.com/orders'
ORDER = dict(order_id='API-001', order_date='2026-10-05', customer='Demo', service='Support', revenue='1500.00', currency='AUD')
PERIOD = DateRange(start='2026-10-01', end='2026-10-31')


def reader(payload):
    return ApiSalesReader(URL, client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))))


@pytest.mark.parametrize('payload', [[], {}, [None], [dict(ORDER, revenue='bad')],
    [{k:v for k,v in ORDER.items() if k != 'revenue'}], [{k:v for k,v in ORDER.items() if k != 'currency'}],
    [dict(ORDER, order_date='2026-02-30')], [dict(ORDER, currency='USD')], [ORDER, ORDER],
    [dict(ORDER, Amount='1500.00')]])
def test_invalid_sales_payload(payload):
    r = reader(payload)
    with r.client, pytest.raises(ReportError):
        r.read()


def test_aliases():
    payload = [dict(zip(['Order Number','Date','Client','Product','Sales Amount','Currency Code'], ORDER.values()))]
    r = reader(payload)
    with r.client:
        assert str(r.read().orders[0].revenue) == '1500.00'


@pytest.mark.parametrize('combined', [False, True])
def test_final_document_and_template(tmp_path, combined):
    before = DEFAULT_TEMPLATE.read_bytes()
    r = reader([ORDER])
    inputs = build_readers([SAMPLES/'sales.csv'], SAMPLES/'monthly_metrics.pdf', 'offline') if combined else []
    with r.client:
        result = ReportService().generate('sales_summary', PERIOD, inputs + [r], tmp_path/'report.docx')
    doc = Document(result.path)
    assert len(doc.inline_shapes) == 1 and len(doc.tables) >= 2
    assert ('AUD 8,500.00' if combined else 'AUD 1,500.00') in doc.tables[0].rows[1].cells[1].text
    assert any('Sales API source: https://example.com/orders' in line.text for line in doc.paragraphs)
    assert DEFAULT_TEMPLATE.read_bytes() == before


def test_duplicate_across_files_and_api(tmp_path):
    r = reader([dict(ORDER, order_id='SO-202610-001')])
    # Use an actual selected file ID, without assuming fixture naming.
    from sources.csv_excel import CsvExcelReader
    payload = dict(ORDER, order_id=CsvExcelReader(SAMPLES/'sales.csv').read().orders[0].order_id)
    r.client.close()
    r = reader([payload])
    with r.client, pytest.raises(ReportError, match='Duplicate order'):
        ReportService().generate('sales_summary', PERIOD, build_readers([SAMPLES/'sales.csv'])+[r], tmp_path/'report.docx')


@pytest.mark.parametrize('failure', ['timeout','http','json','oversized'])
def test_sales_transport_errors(monkeypatch, failure):
    def handler(request):
        if failure == 'timeout':
            raise httpx.ReadTimeout('test', request=request)
        if failure == 'http':
            return httpx.Response(500)
        return httpx.Response(200, content=b'x' * (20*1024*1024+1) if failure == 'oversized' else b'bad json')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client, pytest.raises(ReportError):
        ApiSalesReader(URL, client=client).read()


@pytest.mark.parametrize('url', ['http://example.com/', 'https://127.0.0.1/', 'https://example.com:8080/'])
def test_unsafe_sales_url(url):
    with pytest.raises(ReportError):
        ApiSalesReader(url)


def test_cli_and_ui_api_only(tmp_path, monkeypatch):
    monkeypatch.setattr('sources.api_reader.PublicHTTPTransport', lambda: httpx.MockTransport(lambda request: httpx.Response(200, json=[ORDER])))
    assert main(['--report','sales_summary','--start','2026-10-01','--end','2026-10-31', '--sales-api-url',URL,'--output',str(tmp_path/'cli.docx')]) == 0
    monkeypatch.setattr('renderer.pdf_exporter.export_pdf', lambda data: b'%PDF-test')
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=20).run()
    app.checkbox(key='use_files').uncheck().run()
    app.checkbox(key='use_api').check().run()
    app.selectbox(key='api_kind').select('Sales orders').run()
    app.text_input(key='api_url').set_value(URL).run()
    app.button(key='generate').click().run()
    assert not app.exception and app.success
    assert Document(BytesIO(app.session_state['generated_report']['data'])).inline_shapes

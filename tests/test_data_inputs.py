from pathlib import Path
"""Unified input routing, public endpoint safeguards and UI integration."""
from hashlib import sha256
from io import BytesIO
import socket

from docx import Document
import httpx
from openpyxl import Workbook
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from core.exceptions import ReportError
from core.input_selection import save_uploads
from support import SAMPLES, build_readers
from core.report_service import DEFAULT_TEMPLATE, ReportService
from core.schemas import DateRange
from sources.api_reader import ApiTaskReader

PERIOD = DateRange(start='2026-10-01', end='2026-10-31')
TASKS = [{'userId': 1, 'id': i, 'title': 'Task', 'completed': i == 1} for i in range(1, 4)]


def upload(name, data):
    result = BytesIO(data)
    result.name = name
    return result


@pytest.fixture
def ui(monkeypatch):
    from renderer import pdf_exporter
    monkeypatch.setattr(pdf_exporter, 'export_pdf', lambda data: b'%PDF-test-double')
    return AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=30).run()


def test_csv_upload_is_entirely_offline(ui, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Offline generation must not access the network')
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(httpx.Client, 'get', forbidden)
    monkeypatch.setattr(st, 'file_uploader', lambda *a, **k: [upload('sales.csv', (SAMPLES / 'sales.csv').read_bytes())])
    ui.run()
    assert not ui.multiselect
    assert not ui.text_input
    ui.button(key='generate').click().run()
    assert not ui.exception and ui.success
    assert 'AUD 7,000.00' in ui.session_state['generated_report']['summary']


@pytest.mark.parametrize('sheet,success', [('', True), ('Alternate', True), ('Missing', False)])
def test_xlsx_worksheet_ui(ui, monkeypatch, sheet, success):
    book = Workbook()
    book.active.title = 'First'
    for worksheet in [book.active, book.create_sheet('Alternate')]:
        worksheet.append(['order_id', 'order_date', 'customer', 'service', 'revenue', 'currency'])
        worksheet.append(['X1', '2026-10-01', 'Example', 'Support', '84.00' if worksheet.title == 'Alternate' else '42.00', 'AUD'])
    data = BytesIO()
    book.save(data)
    monkeypatch.setattr(st, 'file_uploader', lambda *a, **k: [upload('sales.xlsx', data.getvalue())])
    ui.run()
    ui.text_input(key='sheet_name').set_value(sheet).run()
    ui.button(key='generate').click().run()
    assert not ui.exception
    if success:
        expected = 'AUD 84.00' if sheet == 'Alternate' else 'AUD 42.00'
        assert ui.success and expected in ui.session_state['generated_report']['summary']
    else:
        assert "'Missing' was not found" in ui.error[0].value
        assert not ui.get('download_button')


def test_unified_upload_and_custom_api_reach_final_docx(ui, monkeypatch):
    monkeypatch.setattr(st, 'file_uploader', lambda *a, **k: [
        upload('sales.csv', (SAMPLES / 'sales.csv').read_bytes()),
        upload('metrics.pdf', (SAMPLES / 'monthly_metrics.pdf').read_bytes())])
    urls = []
    def handler(request):
        urls.append(str(request.url))
        return httpx.Response(200, json=TASKS)
    monkeypatch.setattr('sources.api_reader.PublicHTTPTransport', lambda: httpx.MockTransport(handler))
    ui.run()
    ui.checkbox(key='use_api').check().run()
    ui.text_input(key='api_url').set_value('https://example.com/tasks').run()
    before = sha256(DEFAULT_TEMPLATE.read_bytes()).digest()
    ui.button(key='generate').click().run()
    assert not ui.exception and ui.success
    assert urls == ['https://example.com/tasks']
    document = Document(BytesIO(ui.session_state['generated_report']['data']))
    metrics = {r.cells[0].text: r.cells[1].text for r in document.tables[0].rows[1:]}
    assert metrics['Recorded revenue'] == 'AUD 7,000.00'
    assert metrics['Sales target'] == 'AUD 8,000.00'
    tasks = {r.cells[0].text: r.cells[1].text for r in document.tables[-1].rows[1:]}
    assert tasks['Total tasks'] == '3' and tasks['Completion rate'] == '33.3%'
    assert sha256(DEFAULT_TEMPLATE.read_bytes()).digest() == before
    ui.text_input(key='api_url').set_value('https://example.com/other').run()
    assert not ui.get('download_button')


def test_api_only_operations_and_missing_sales(ui, monkeypatch):
    monkeypatch.setattr('sources.api_reader.PublicHTTPTransport', lambda: httpx.MockTransport(
        lambda request: httpx.Response(200, json=TASKS)))
    ui.checkbox(key='use_files').uncheck().run()
    ui.checkbox(key='use_api').check().run()
    ui.button(key='generate').click().run()
    assert 'requires sales data' in ui.error[0].value
    ui.selectbox(key='report_type').select('operations_kpi').run()
    ui.button(key='generate').click().run()
    assert not ui.exception and ui.success
    document = Document(BytesIO(ui.session_state['generated_report']['data']))
    assert document.tables and document.inline_shapes


@pytest.mark.parametrize('name,data', [('bad.exe', b'x'), ('bad.csv', b'wrong,columns\n1,2'),
                                     ('bad.xlsx', b'not a workbook'), ('bad.pdf', b'not a PDF')])
def test_unsupported_or_disguised_uploads_fail(tmp_path, name, data):
    with pytest.raises(ReportError):
        sales, pdf = save_uploads([upload(name, data)], tmp_path)
        ReportService().generate('sales_summary', PERIOD,
            build_readers(sales, pdf, 'offline'), tmp_path / 'out.docx')
    assert not (tmp_path / 'out.docx').exists()


def test_multiple_pdf_files_rejected(tmp_path):
    with pytest.raises(ReportError, match='at most one PDF'):
        save_uploads([upload('a.pdf', b'a'), upload('b.PDF', b'b')], tmp_path)
    assert not list(tmp_path.iterdir())


def test_multiple_sales_reject_duplicate_orders(tmp_path):
    data = (SAMPLES / 'sales.csv').read_bytes()
    sales, pdf = save_uploads([upload('a.csv', data), upload('b.csv', data)], tmp_path)
    with pytest.raises(ReportError, match='[Dd]uplicate|unique'):
        ReportService().generate('sales_summary', PERIOD, build_readers(sales, pdf), tmp_path / 'out.docx')


@pytest.mark.parametrize('url', ['', 'example.com', 'http://example.com/tasks',
    'https://localhost/tasks', 'https://server.internal/tasks', 'https://127.0.0.1/tasks',
    'https://10.0.0.1/', 'https://169.254.169.254/', 'https://[::1]/',
    'https://[::ffff:127.0.0.1]/', 'https://example.com:8443/', 'https://user:password@example.com/',
    'https://example.com/#fragment', 'https://example.com/\n', 'https://2130706433/',
    'https://example.com\\@localhost/', 'https://example.com:bad/'])
def test_bad_urls_rejected_without_dns(monkeypatch, url):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: pytest.fail('Unexpected DNS lookup'))
    with pytest.raises(ReportError, match='public HTTPS'):
        ApiTaskReader(url=url)


@pytest.mark.parametrize('addresses', [['127.0.0.1'], ['10.1.2.3'], ['169.254.169.254'],
    ['::1'], ['93.184.216.34', '192.168.1.2'], ['100.64.0.1'], ['224.0.0.1']])
def test_dns_private_or_mixed_answers_are_blocked(monkeypatch, addresses):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [(0, 0, 0, '', (address, 443)) for address in addresses])
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', lambda *a: pytest.fail('Blocked address connected'))
    with pytest.raises(ReportError, match='public IP'):
        ApiTaskReader(url='https://example.com/tasks').read()


def test_transport_pins_ip_and_preserves_tls_name(monkeypatch):
    resolved = []
    def resolve(*args, **kwargs):
        resolved.append(args[0])
        return [(0, 0, 0, '', ('93.184.216.34', 443))]
    monkeypatch.setattr(socket, 'getaddrinfo', resolve)
    def send(self, request):
        assert request.url.host == '93.184.216.34'
        assert request.headers['host'] == 'example.com'
        assert request.extensions['sni_hostname'] == 'example.com'
        assert request.url.path == '/tasks' and request.url.query == b'limit=3'
        return httpx.Response(200, json=TASKS)
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', send)
    snapshot = ApiTaskReader(url='https://example.com/tasks?limit=3').read().snapshot
    assert resolved == ['example.com']
    assert snapshot.source == 'https://example.com/tasks?limit=3'


def test_dns_failure_is_recoverable(monkeypatch):
    def fail(*args, **kwargs):
        raise socket.gaierror('unavailable')
    monkeypatch.setattr(socket, 'getaddrinfo', fail)
    with pytest.raises(ReportError, match='Cannot resolve'):
        ApiTaskReader().read()


def test_redirect_is_not_followed(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request.url)
        return httpx.Response(302, headers={'location': 'https://127.0.0.1/private'})
    monkeypatch.setattr('sources.api_reader.PublicHTTPTransport', lambda: httpx.MockTransport(handler))
    with pytest.raises(ReportError, match='HTTP 302'):
        ApiTaskReader().read()
    assert len(calls) == 1


def test_task_pdf_upload(ui, monkeypatch):
    path = Path(__file__).resolve().parents[1]/'sample_data/Operations_KPI_Dummy_Data/operations_tasks_2026-11.pdf'
    monkeypatch.setattr(st, 'file_uploader', lambda *a, **k: [upload('tasks.pdf', path.read_bytes())])
    ui.selectbox(key='report_type').select('operations_kpi').run()
    assert not ui.text_input
    ui.button(key='generate').click().run()
    assert not ui.exception and ui.success
    assert '70.0%' in ui.session_state['generated_report']['summary']


def test_multiple_distinct_sales_files_combine(tmp_path):
    header = b'order_id,order_date,customer,service,revenue,currency\n'
    inputs = [upload('a.csv', header + b'A,2026-10-01,Example,Support,10.00,AUD\n'),
              upload('b.csv', header + b'B,2026-10-02,Example,Support,20.00,AUD\n')]
    sales, pdf = save_uploads(inputs, tmp_path)
    result = ReportService().generate('sales_summary', PERIOD, build_readers(sales, pdf), tmp_path / 'out.docx')
    assert 'AUD 30.00 from 2 orders' in result.content.summary

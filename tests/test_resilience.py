"""Regression checks for realistic inputs, repeated runs and recoverable failures."""
import csv
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from docx import Document
import pytest
from streamlit.testing.v1 import AppTest

from core.exceptions import DataValidationError, SourceReadError
from core.input_selection import MAX_UPLOAD_BYTES, SAMPLES, build_readers, save_upload
from core.report_service import DEFAULT_TEMPLATE, ReportService
from core.schemas import DateRange
from sources.api_reader import ApiTaskReader
from sources.csv_excel import COLUMNS, CsvExcelReader

ROOT = Path(__file__).resolve().parents[1]
PERIOD = DateRange(start='2026-10-01', end='2026-10-31')


def write_sales(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(COLUMNS)
        writer.writerows(rows)


@pytest.mark.parametrize('customer,service', [
    ('中文客户，研发部门 & <测试>', '系统维护与数据备份'),
    ('Very long customer name ' * 40, 'Implementation and support ' * 50),
])
def test_long_and_unicode_text_survive_csv_to_docx(tmp_path, customer, service):
    source = tmp_path / '销售 数据.csv'
    write_sales(source, [('0001', '2026-10-01', customer, service, '0.10', 'AUD'),
                         ('0002', '2026-10-31', 'Other', 'Support', '0.20', 'AUD')])
    result = ReportService().generate('sales_summary', PERIOD, [CsvExcelReader(source)], tmp_path / '报告 with spaces.docx')
    doc = Document(result.path)
    assert doc.tables[1].rows[1].cells[0].text == '0001'
    assert doc.tables[1].rows[1].cells[2].text == customer.strip()
    assert doc.tables[1].rows[1].cells[3].text == service.strip()
    assert doc.tables[0].rows[1].cells[1].text == 'AUD 0.30'
    assert len(doc.inline_shapes) == 1
    # Content round-trip is not a visual pagination or font-availability check.


def test_large_csv_reads_every_row_without_losing_cents(tmp_path):
    source = tmp_path / 'large.csv'
    write_sales(source, ((str(i), '2026-10-15', 'Synthetic', 'Support', '0.01', 'AUD') for i in range(10000)))
    data = CsvExcelReader(source).read()
    assert len(data.orders) == 10000
    assert data.orders[0].order_id == '0'
    assert data.orders[-1].order_id == '9999'
    assert sum(o.revenue for o in data.orders) == Decimal('100.00')


def test_repeated_service_runs_do_not_accumulate_rows_or_change_template(tmp_path):
    service = ReportService()
    before = sha256(DEFAULT_TEMPLATE.read_bytes()).hexdigest()
    readers = build_readers([SAMPLES / 'sales.csv'], SAMPLES / 'monthly_metrics.pdf', 'offline')
    fingerprints = []
    for i in range(5):
        kind = 'sales_summary' if i % 2 == 0 else 'operations_kpi'
        result = service.generate(kind, PERIOD, readers, tmp_path / ('run_{}.docx'.format(i)))
        doc = Document(result.path)
        assert len(doc.inline_shapes) == 1
        fingerprints.append((kind, [[tuple(c.text for c in row.cells) for row in table.rows] for table in doc.tables]))
    assert fingerprints[0] == fingerprints[2] == fingerprints[4]
    assert fingerprints[1] == fingerprints[3]
    assert sha256(DEFAULT_TEMPLATE.read_bytes()).hexdigest() == before


@pytest.mark.parametrize('size,accepted', [(MAX_UPLOAD_BYTES, True), (MAX_UPLOAD_BYTES + 1, False)])
def test_upload_size_limit_exact_boundary(tmp_path, size, accepted):
    upload = BytesIO(b'x' * size)
    upload.name = 'boundary.csv'
    if accepted:
        assert save_upload(upload, tmp_path, 'input', ('.csv',)).stat().st_size == size
    else:
        with pytest.raises(DataValidationError, match='20 MB'):
            save_upload(upload, tmp_path, 'input', ('.csv',))
        assert not list(tmp_path.iterdir())
    # This tests admission size, not whether the artificial bytes form valid CSV.


def start_app():
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
    assert not app.exception
    return app


def test_two_app_sessions_keep_results_and_settings_separate():
    first, second = start_app(), start_app()
    first.button(key='generate').click().run()
    saved = first.session_state['generated_report']['data']
    second.selectbox(key='report_type').select('operations_kpi').run()
    second.button(key='generate').click().run()
    assert second.session_state['generated_report']['filename'].startswith('operations_kpi')
    first.run()
    assert first.selectbox(key='report_type').value == 'sales_summary'
    assert first.session_state['generated_report']['data'] == saved
    second.multiselect(key='sources').set_value([]).run()
    second.button(key='generate').click().run()
    assert second.error and not second.get('download_button')
    first.run()
    assert first.get('download_button')
    assert first.session_state['generated_report']['data'] == saved
    assert not first.exception and not second.exception
    # Independent AppTest sessions are not a simultaneous-browser load test.


def test_repeated_ui_generation_replaces_result_without_duplicating_controls():
    app = start_app()
    for _ in range(3):
        app.button(key='generate').click().run()
        assert not app.exception
        assert len(app.success) == 1
        assert len(app.get('download_button')) == 2
        doc = Document(BytesIO(app.session_state['generated_report']['data']))
        assert len(doc.tables[1].rows) == 5
        assert len(doc.inline_shapes) == 1


def test_live_api_failure_clears_old_download_and_recovers_in_same_session(monkeypatch):
    app = start_app()
    app.button(key='generate').click().run()
    assert app.get('download_button')
    def fail(self):
        raise SourceReadError('Task API timed out. Please try again.')
    monkeypatch.setattr(ApiTaskReader, 'read', fail)
    app.selectbox(key='task_mode').select('live').run()
    app.button(key='generate').click().run()
    assert not app.exception
    assert 'timed out' in app.error[0].value
    assert not app.get('download_button')
    app.selectbox(key='task_mode').select('offline').run()
    app.button(key='generate').click().run()
    assert not app.exception and not app.error
    assert app.success and app.get('download_button')
    assert app.session_state['generated_report']['filename'].endswith('_offline.docx')


@pytest.fixture(autouse=True)
def stub_optional_pdf_export(monkeypatch):
    # UI regression tests remain independent of an installed office application.
    # Real conversion and PDF error handling have separate verification.
    from renderer import pdf_exporter
    monkeypatch.setattr(pdf_exporter, 'export_pdf', lambda data: b'%PDF-test-double')

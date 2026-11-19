from pathlib import Path
from unittest.mock import Mock
from zipfile import ZipFile

import httpx
import pytest

from core.exceptions import DataValidationError, ReportError, SourceReadError
from core.input_selection import save_upload
from support import SAMPLES, build_readers
from core.report_service import ReportService
from core.schemas import DateRange
from sources.api_reader import ApiTaskReader

PERIOD = DateRange(start='2026-10-01', end='2026-10-31')


@pytest.mark.parametrize('kind', ['sales_summary', 'operations_kpi'])
def test_shared_pipeline_creates_docx(tmp_path, kind):
    readers = build_readers([SAMPLES / 'sales.csv'], SAMPLES / 'monthly_metrics.pdf', 'offline')
    result = ReportService().generate(kind, PERIOD, readers, tmp_path / (kind + '.docx'))
    assert result.content.report_type == kind
    with ZipFile(result.path) as archive:
        assert b'Executive summary' in archive.read('word/document.xml')


def test_live_api_pipeline_uses_actual_response_not_fixture(tmp_path):
    tasks = [{'id': 1, 'userId': 1, 'title': 'HTTP mock task', 'completed': True}]
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=tasks))) as client:
        readers = build_readers([SAMPLES / 'sales.csv'], SAMPLES / 'monthly_metrics.pdf') + [ApiTaskReader(client)]
        result = ReportService().generate('sales_summary', PERIOD, readers, tmp_path / 'live.docx')
    assert result.content.tables[-1].rows[0] == ('Total tasks', '1')
    assert 'live_demo' in ' '.join(result.content.notes)


@pytest.mark.parametrize('kind,readers,message', [
    ('unknown', [], 'supported report'),
    ('sales_summary', [], 'at least one'),
    ('sales_summary', build_readers(task_mode='offline'), 'requires sales data'),
    ('operations_kpi', build_readers([SAMPLES / 'sales.csv']), 'requires a task snapshot'),
])
def test_missing_requirements_do_not_write_files(tmp_path, kind, readers, message):
    output = tmp_path / 'out.docx'
    with pytest.raises(DataValidationError, match=message):
        ReportService().generate(kind, PERIOD, readers, output)
    assert not output.exists()


def test_failed_api_is_logged_without_partial_report(tmp_path, caplog):
    reader = Mock()
    reader.read.side_effect = SourceReadError('Task API timed out')
    with pytest.raises(SourceReadError):
        ReportService().generate('operations_kpi', PERIOD, [reader], tmp_path / 'out.docx')
    assert not (tmp_path / 'out.docx').exists()
    assert 'timed out' in caplog.text


def test_unexpected_failure_gets_clear_boundary_error(tmp_path, caplog):
    reader = Mock()
    reader.read.side_effect = RuntimeError('test failure')
    with pytest.raises(ReportError, match='unexpected error'):
        ReportService().generate('sales_summary', PERIOD, [reader], tmp_path / 'out.docx')
    assert 'Unexpected report generation failure' in caplog.text


def test_upload_names_cannot_escape_temp_directory(tmp_path):
    upload = Mock(name='upload')
    upload.name = '../../outside.csv'
    upload.getvalue.return_value = b'example'
    output = save_upload(upload, tmp_path, 'sales_0', ('.csv', '.xlsx'))
    assert output == tmp_path / 'sales_0.csv'
    assert output.read_bytes() == b'example'


@pytest.mark.parametrize('name,data,message', [('file.exe', b'x', 'Unsupported'), ('file.csv', b'', 'empty'), ('file.csv', b'x' * (20 * 1024 * 1024 + 1), '20 MB')])
def test_upload_validation(tmp_path, name, data, message):
    upload = Mock()
    upload.name = name
    upload.getvalue.return_value = data
    with pytest.raises(DataValidationError, match=message):
        save_upload(upload, tmp_path, 'input', ('.csv',))
    assert not list(tmp_path.iterdir())


def test_new_reader_and_report_use_existing_pipeline(tmp_path):
    """An extension can generate DOCX without changing existing readers/builders."""
    from docx import Document
    from core.schemas import SalesOrder, SourceData
    from reports.base import ReportData
    from reports.sales_summary import SalesSummaryBuilder

    class MemoryReader:
        def read(self):
            return SourceData(orders=[SalesOrder(order_id='EXT-1', order_date='2026-10-15',
                customer='Extension Demo', service='Support', revenue='123.45')])

    class CustomBuilder:
        def build(self, data, period):
            values = SalesSummaryBuilder().build(data, period).model_dump()
            values.update(report_type='custom_sales', title='Custom Sales')
            return ReportData.model_validate(values)

    service = ReportService(builders={'custom_sales': CustomBuilder()})
    result = service.generate('custom_sales', PERIOD, [MemoryReader()], tmp_path / 'custom.docx')
    assert result.content.report_type == 'custom_sales'
    document = Document(result.path)
    assert document.paragraphs[0].text == 'Custom Sales'
    assert document.tables[0].rows[1].cells[1].text == 'AUD 123.45'
    assert document.tables[1].rows[1].cells[0].text == 'EXT-1'


def test_three_sources_reach_final_document(tmp_path):
    from docx import Document
    tasks = [{'id': i, 'userId': 1, 'title': 'Synthetic task {}'.format(i),
              'completed': i == 1} for i in range(1, 4)]
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=tasks))) as client:
        readers = build_readers([SAMPLES / 'sales.csv'], SAMPLES / 'monthly_metrics.pdf') + [ApiTaskReader(client)]
        result = ReportService().generate('sales_summary', PERIOD, readers, tmp_path / 'combined.docx')
    document = Document(result.path)
    metrics = {r.cells[0].text: r.cells[1].text for r in document.tables[0].rows[1:]}
    assert metrics['Recorded revenue'] == 'AUD 7,000.00'
    assert metrics['Sales target'] == 'AUD 8,000.00'
    assert metrics['Target achievement'] == '87.5%'
    tasks_table = {r.cells[0].text: r.cells[1].text for r in document.tables[-1].rows[1:]}
    assert tasks_table['Total tasks'] == '3'
    assert tasks_table['Completed'] == '1'
    assert tasks_table['Completion rate'] == '33.3%'

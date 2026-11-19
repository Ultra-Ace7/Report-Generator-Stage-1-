import pytest
from datetime import date
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from streamlit.testing.v1 import AppTest

from core.exceptions import SourceReadError
from sources.api_reader import ApiTaskReader

APP = Path(__file__).resolve().parents[1] / 'app.py'


def start_app():
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not app.exception
    return app


def test_sales_generate_download_and_input_change_hides_stale_result():
    app = start_app()
    app.button(key='generate').click().run()
    assert not app.exception
    assert app.success
    result = app.session_state['generated_report']
    assert result['filename'].endswith('_offline.docx')
    with ZipFile(BytesIO(result['data'])) as archive:
        assert b'AUD 7,000.00' in archive.read('word/document.xml')
    assert len(app.get('download_button')) == 2
    app.date_input(key='end_date').set_value(date(2026, 10, 30)).run()
    assert not app.get('download_button')


def test_operations_ui_requires_task_snapshot():
    app = start_app()
    app.selectbox(key='report_type').select('operations_kpi').run()
    app.multiselect(key='sources').set_value(['Sales files']).run()
    app.button(key='generate').click().run()
    assert not app.exception
    assert 'requires a task snapshot' in app.error[0].value
    assert not app.get('download_button')


def test_operations_offline_ui():
    app = start_app()
    app.selectbox(key='report_type').select('operations_kpi').run()
    app.multiselect(key='sources').set_value(['Task snapshot']).run()
    app.button(key='generate').click().run()
    assert not app.exception
    assert app.success
    assert '60.0%' in app.session_state['generated_report']['summary']


def test_reversed_dates_show_error():
    app = start_app()
    app.date_input(key='start_date').set_value(date(2026, 11, 1)).run()
    app.button(key='generate').click().run()
    assert not app.exception
    assert 'Start date must' in app.error[0].value


def test_upload_mode_missing_files_shows_error():
    app = start_app()
    app.radio(key='file_mode').set_value('Upload files').run()
    app.button(key='generate').click().run()
    assert not app.exception
    assert 'Upload at least one' in app.error[0].value


def test_api_failure_shows_error_and_no_download(monkeypatch):
    def fail(self):
        raise SourceReadError('Task API timed out. Please try again.')
    monkeypatch.setattr(ApiTaskReader, 'read', fail)
    app = start_app()
    app.selectbox(key='task_mode').select('live').run()
    app.button(key='generate').click().run()
    assert not app.exception
    assert 'timed out' in app.error[0].value
    assert not app.get('download_button')


def test_uploaded_files_flow_uses_uploaded_sales(monkeypatch):
    from io import BytesIO
    import streamlit as st
    from core.input_selection import SAMPLES
    sales = BytesIO(b'order_id,order_date,customer,service,revenue,currency\nUP-1,2026-10-15,Upload Demo,Support,80.00,AUD\n')
    sales.name = 'my_sales.csv'
    pdf = BytesIO((SAMPLES / 'monthly_metrics.pdf').read_bytes())
    pdf.name = 'targets.pdf'
    def upload(*args, **kwargs):
        return [sales] if kwargs.get('accept_multiple_files') else pdf
    monkeypatch.setattr(st, 'file_uploader', upload)
    app = start_app()
    app.radio(key='file_mode').set_value('Upload files').run()
    app.button(key='generate').click().run()
    assert not app.exception
    assert app.success
    assert 'AUD 80.00 from 1 orders' in app.session_state['generated_report']['summary']
    with ZipFile(BytesIO(app.session_state['generated_report']['data'])) as archive:
        assert b'UP-1' in archive.read('word/document.xml')


def test_bad_uploaded_file_shows_error_and_application_recovers(monkeypatch):
    import streamlit as st
    bad = BytesIO(b'not,the,required,columns\n1,2,3,4\n')
    bad.name = 'bad.csv'
    monkeypatch.setattr(st, 'file_uploader', lambda *args, **kwargs: [bad])
    app = start_app()
    app.multiselect(key='sources').set_value(['Sales files']).run()
    app.radio(key='file_mode').set_value('Upload files').run()
    app.button(key='generate').click().run()
    assert not app.exception
    assert app.error
    assert not app.get('download_button')
    app.radio(key='file_mode').set_value('Sample files').run()
    app.button(key='generate').click().run()
    assert not app.exception
    assert app.success
    assert app.get('download_button')


@pytest.fixture(autouse=True)
def stub_optional_pdf_export(monkeypatch):
    # UI regression tests remain independent of an installed office application.
    # Real conversion and PDF error handling have separate verification.
    from renderer import pdf_exporter
    monkeypatch.setattr(pdf_exporter, 'export_pdf', lambda data: b'%PDF-test-double')

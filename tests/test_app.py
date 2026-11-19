from datetime import date
from io import BytesIO
from pathlib import Path
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from core.exceptions import SourceReadError
from sources.api_reader import ApiTaskReader

ROOT=Path(__file__).resolve().parents[1]
SALES=ROOT/'sample_data/Sales_Summary_Dummy_Data/sales_2026-10.csv'
TASKS=ROOT/'sample_data/Operations_KPI_Dummy_Data/operations_tasks_2026-10.csv'


def uploaded(path):
    data=BytesIO(path.read_bytes());data.name=path.name
    return data


@pytest.fixture(autouse=True)
def stub_pdf(monkeypatch):
    monkeypatch.setattr('renderer.pdf_exporter.export_pdf',lambda data:b'%PDF-test')


def start_app():
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=20).run()
    assert not app.exception
    return app


def test_sales_generate_download_and_input_change_hides_stale_result(monkeypatch):
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:[uploaded(SALES)])
    app=start_app();app.button(key='generate').click().run()
    assert app.success and not app.exception
    assert 'AUD 7,390.00' in app.session_state['generated_report']['summary']
    assert len(app.get('download_button'))==2
    app.date_input(key='end_date').set_value(date(2026,10,30)).run()
    assert not app.get('download_button')


def test_operations_ui_requires_task_snapshot():
    app=start_app();app.selectbox(key='report_type').select('operations_kpi').run()
    app.checkbox(key='use_files').uncheck().run()
    app.button(key='generate').click().run()
    assert not app.exception and 'requires a task snapshot' in app.error[0].value


def test_operations_uploaded_ui(monkeypatch):
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:[uploaded(TASKS)])
    app=start_app();app.selectbox(key='report_type').select('operations_kpi').run()
    app.button(key='generate').click().run()
    assert not app.exception and app.success
    assert '75.0%' in app.session_state['generated_report']['summary']


def test_reversed_dates_show_error():
    app=start_app();app.date_input(key='start_date').set_value(date(2026,11,1)).run()
    app.button(key='generate').click().run()
    assert not app.exception and 'Start date must' in app.error[0].value


def test_upload_mode_missing_files_shows_error():
    app=start_app();app.button(key='generate').click().run()
    assert not app.exception and 'Upload at least one' in app.error[0].value
    assert [item.key for item in app.checkbox]==['use_files','use_api']


def test_api_failure_shows_error_and_no_download(monkeypatch):
    def fail(self):
        raise SourceReadError('Task API timed out.')
    monkeypatch.setattr(ApiTaskReader,'read',fail)
    app=start_app();app.selectbox(key='report_type').select('operations_kpi').run()
    app.checkbox(key='use_files').uncheck().run();app.checkbox(key='use_api').check().run()
    app.button(key='generate').click().run()
    assert not app.exception and 'timed out' in app.error[0].value
    assert not app.get('download_button')


def test_uploaded_files_flow_uses_uploaded_sales(monkeypatch):
    data=BytesIO(b'order_id,order_date,customer,service,revenue,currency\nUP-1,2026-10-15,Upload Demo,Support,80.00,AUD\n');data.name='custom.csv'
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:[data])
    app=start_app();app.button(key='generate').click().run()
    assert not app.exception and app.success
    assert 'AUD 80.00 from 1 orders' in app.session_state['generated_report']['summary']


def test_bad_uploaded_file_shows_error_and_application_recovers(monkeypatch):
    bad=BytesIO(b'wrong,columns\n1,2');bad.name='bad.csv'
    uploads=[bad]
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:uploads)
    app=start_app();app.button(key='generate').click().run()
    assert app.error and not app.get('download_button')
    uploads[:]=[uploaded(SALES)]
    app.run();app.button(key='generate').click().run()
    assert not app.exception and app.success

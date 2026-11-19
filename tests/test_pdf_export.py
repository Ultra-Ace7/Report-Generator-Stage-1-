from datetime import date
from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest
from streamlit.testing.v1 import AppTest

from renderer import pdf_exporter
from scripts import export_pdf as command

ROOT = Path(__file__).resolve().parents[1]
PDF = (ROOT / 'sample_data/monthly_metrics.pdf').read_bytes()


def test_converter_preserves_input_and_uses_isolated_profile(monkeypatch):
    monkeypatch.setattr(pdf_exporter, 'find_converter', lambda: '/test/soffice')
    profiles = []
    def run(args, **kwargs):
        assert kwargs['timeout'] == 60
        assert kwargs['capture_output'] and not kwargs['check']
        profiles.append(args[1])
        assert Path(args[-1]).read_bytes() == b'original document'
        (Path(args[args.index('--outdir') + 1]) / 'report.pdf').write_bytes(PDF)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(pdf_exporter.subprocess, 'run', run)
    for _ in range(2):
        assert pdf_exporter.export_pdf(b'original document') == PDF
    assert profiles[0] != profiles[1]


@pytest.mark.parametrize('failure', ['timeout', 'process', 'missing', 'invalid', 'permission'])
def test_conversion_failures_are_clear_and_logged(monkeypatch, failure, caplog):
    monkeypatch.setattr(pdf_exporter, 'find_converter', lambda: '/test/soffice')
    def run(args, **kwargs):
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(args, 60)
        if failure == 'permission':
            raise PermissionError('test')
        if failure == 'invalid':
            (Path(args[args.index('--outdir') + 1]) / 'report.pdf').write_bytes(b'not pdf')
        return SimpleNamespace(returncode=1 if failure == 'process' else 0)
    monkeypatch.setattr(pdf_exporter.subprocess, 'run', run)
    with pytest.raises(pdf_exporter.PdfExportError):
        pdf_exporter.export_pdf(b'docx')
    assert caplog.records


def test_bad_config_reports_setup_error(monkeypatch, tmp_path):
    monkeypatch.setenv('LIBREOFFICE_PATH', str(tmp_path / 'missing'))
    with pytest.raises(pdf_exporter.PdfExportError, match='configured'):
        pdf_exporter.export_pdf(b'docx')


def test_ui_pdf_success_uses_existing_word_and_resets_on_input_change(monkeypatch):
    seen = []
    def convert(data):
        seen.append(data)
        return PDF
    monkeypatch.setattr(pdf_exporter, 'export_pdf', convert)
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
    app.button(key='generate').click().run()
    original = app.session_state['generated_report']['data']
    assert not app.exception
    assert seen == [original]
    assert app.session_state['generated_report']['pdf'] == PDF
    assert len(app.get('download_button')) == 2
    app.date_input(key='end_date').set_value(date(2026, 10, 30)).run()
    assert not app.get('download_button')


def test_ui_pdf_failure_preserves_word_and_can_retry(monkeypatch):
    def fail(data):
        raise pdf_exporter.PdfExportError('PDF conversion timed out.')
    monkeypatch.setattr(pdf_exporter, 'export_pdf', fail)
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
    app.button(key='generate').click().run()
    original = app.session_state['generated_report']['data']
    assert not app.exception and app.warning
    assert len(app.get('download_button')) == 2
    assert app.get('download_button')[1].proto.disabled
    assert app.session_state['generated_report']['data'] == original
    monkeypatch.setattr(pdf_exporter, 'export_pdf', lambda data: PDF)
    app.button(key='generate').click().run()
    assert not app.get('download_button')[1].proto.disabled
    assert not app.exception and not app.warning
    assert len(app.get('download_button')) == 2


def test_cli_writes_pdf_and_refuses_overwrite(monkeypatch, tmp_path):
    source, output = tmp_path / 'in.docx', tmp_path / 'out.pdf'
    source.write_bytes(b'original')
    monkeypatch.setattr(command, 'export_pdf', lambda data: PDF)
    assert command.main([str(source), str(output)]) == 0
    assert output.read_bytes() == PDF
    assert command.main([str(source), str(output)]) == 1
    assert output.read_bytes() == PDF
    assert source.read_bytes() == b'original'

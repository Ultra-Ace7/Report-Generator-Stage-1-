from pathlib import Path
import subprocess
import sys

import pytest

import cli
from support import SAMPLES

ROOT = Path(__file__).resolve().parents[1]


def args(output):
    return ['--report', 'sales_summary', '--start', '2026-10-01', '--end', '2026-10-31',
            '--sales', str(ROOT / 'sample_data/Sales_Summary_Dummy_Data/sales_2026-10.csv'), '--output', str(output)]


def test_cli_runs_from_another_working_directory(tmp_path):
    output = tmp_path / 'sales.docx'
    result = subprocess.run([sys.executable, str(ROOT / 'cli.py')] + args(output), cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert output.exists()
    assert 'Report saved:' in result.stdout


def test_cli_invalid_date_returns_one_without_traceback(tmp_path, capsys):
    values = args(tmp_path / 'bad.docx')
    values[values.index('--start') + 1] = '2027-01-01'
    assert cli.main(values) == 1
    assert 'Start date must' in capsys.readouterr().err
    assert not (tmp_path / 'bad.docx').exists()


def test_cli_missing_file_returns_one(tmp_path, capsys):
    values = args(tmp_path / 'bad.docx')
    values[values.index('--sales') + 1] = str(tmp_path / 'missing.csv')
    assert cli.main(values) == 1
    error = capsys.readouterr().err
    assert 'cannot read input' in error
    assert 'Traceback' not in error


def test_cli_duplicate_inputs_are_rejected(tmp_path, capsys):
    assert cli.main(args(tmp_path / 'duplicate.docx') + ['--sales', str(ROOT / 'sample_data/Sales_Summary_Dummy_Data/sales_2026-10.csv')]) == 1
    assert 'Duplicate order' in capsys.readouterr().err


def test_cli_never_overwrites_existing_output(tmp_path, capsys):
    output = tmp_path / 'existing.docx'
    output.write_bytes(b'original')
    assert cli.main(args(output)) == 1
    assert output.read_bytes() == b'original'


def test_cli_operations_with_only_tasks(tmp_path, capsys, monkeypatch):
    from sources.api_reader import ApiTaskReader, OfflineTaskReader
    monkeypatch.setattr(ApiTaskReader, "read", lambda self: OfflineTaskReader(SAMPLES/"todos_fixture.json", SAMPLES/"todos_fixture_metadata.json").read())
    assert cli.main(['--report', 'operations_kpi', '--start', '2026-10-01', '--end', '2026-10-31',
                     '--tasks', 'live', '--output', str(tmp_path / 'operations.docx')]) == 0


def test_cli_custom_task_api_url(tmp_path, monkeypatch):
    import httpx
    seen=[]
    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200,json=[{'userId':1,'id':1,'title':'Task','completed':True}])
    monkeypatch.setattr('sources.api_reader.PublicHTTPTransport',lambda:httpx.MockTransport(handler))
    assert cli.main(['--report','operations_kpi','--start','2026-10-01','--end','2026-10-31',
        '--tasks','live','--task-api-url','https://example.com/tasks','--output',str(tmp_path/'custom.docx')])==0
    assert seen==['https://example.com/tasks']

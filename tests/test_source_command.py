from core.exceptions import SourceReadError
from scripts import check_sources


def test_offline_source_command(tmp_path, monkeypatch, capsys):
    # Keep this test's logs separate from the real project.
    from shutil import copytree
    copytree(check_sources.ROOT / "sample_data", tmp_path / "sample_data")
    monkeypatch.setattr(check_sources, "ROOT", tmp_path)
    assert check_sources.main([]) == 0
    output = capsys.readouterr().out
    assert "offline_fixture" in output
    assert "Sales orders: 8" in output
    assert "Monthly targets: 2" in output
    assert "Tasks: 5 | Completed: 3" in output


def test_source_command_reports_failure_without_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check_sources, "ROOT", tmp_path)
    def fail(self):
        raise SourceReadError("Missing demo input")
    monkeypatch.setattr(check_sources.CsvExcelReader, "read", fail)
    assert check_sources.main([]) == 1
    error = capsys.readouterr().err
    assert "Missing demo input" in error
    assert "Traceback" not in error

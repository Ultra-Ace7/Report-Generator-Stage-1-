import json
from shutil import copytree

from scripts import preview_reports


def test_preview_writes_both_reports_and_charts(tmp_path, monkeypatch, capsys):
    copytree(preview_reports.ROOT / "sample_data", tmp_path / "sample_data")
    monkeypatch.setattr(preview_reports, "ROOT", tmp_path)
    assert preview_reports.main([]) == 0
    files = list((tmp_path / "output" / "preview").iterdir())
    assert len(files) == 4
    sales = json.loads(next(path for path in files if path.name.startswith("sales") and path.suffix == ".json").read_text())
    assert sales["report_type"] == "sales_summary"
    assert len(sales["tables"][0]["rows"]) == 4
    assert "offline_fixture" in " ".join(sales["notes"])
    assert "No Word reports" in capsys.readouterr().out


def test_bad_date_range_fails_without_writing_previews(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(preview_reports, "ROOT", tmp_path)
    assert preview_reports.main(["--start", "2026-11-01", "--end", "2026-10-01"]) == 1
    assert not (tmp_path / "output").exists()
    assert "Start date must" in capsys.readouterr().err

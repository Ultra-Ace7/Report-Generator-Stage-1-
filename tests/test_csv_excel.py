import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from core.exceptions import ReportError
from sources.base import merge_sources
from sources.csv_excel import COLUMNS, CsvExcelReader

SAMPLES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
ROW = ["SO-1", "2026-10-01", "Demo Co", "Support", "10.20", "AUD"]


def csv_file(tmp_path, rows, header=COLUMNS):
    path = tmp_path / "sales.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def excel_file(tmp_path, rows, sheet="Sales"):
    # Disposable test workbook; not an authored user-facing spreadsheet.
    path = tmp_path / "sales.xlsx"
    workbook = Workbook()
    workbook.active.title = sheet
    workbook.active.append(COLUMNS)
    for row in rows:
        workbook.active.append(row)
    workbook.save(path)
    workbook.close()
    return path


def test_csv_preserves_identifiers_and_money_and_skips_blank_rows(tmp_path):
    row = ["0001", "2026-10-01", " Demo Co ", "Support", "0.10", "AUD"]
    result = CsvExcelReader(csv_file(tmp_path, [row, []])).read()
    assert result.orders[0].order_id == "0001"
    assert result.orders[0].customer == "Demo Co"
    assert result.orders[0].revenue == Decimal("0.10")


def test_csv_sample():
    result = CsvExcelReader(SAMPLES / "sales.csv").read()
    assert len(result.orders) == 8
    assert sum(o.revenue for o in result.orders) == Decimal("15000.00")


def test_excel_and_csv_normalize_to_same_models(tmp_path):
    excel_row = list(ROW)
    excel_row[1] = datetime(2026, 10, 1)
    excel_row[4] = 10.20
    assert CsvExcelReader(excel_file(tmp_path, [excel_row])).read() == CsvExcelReader(csv_file(tmp_path, [ROW])).read()


def test_reordered_headers(tmp_path):
    result = CsvExcelReader(csv_file(tmp_path, [list(reversed(ROW))], tuple(reversed(COLUMNS)))).read()
    assert result.orders[0].revenue == Decimal("10.20")


@pytest.mark.parametrize("rows,header,message", [
    ([], COLUMNS, "no orders"),
    ([ROW], COLUMNS[:-1], "Missing required sales fields: currency"),
    ([ROW], ("order_id",) * 6, "Multiple columns map"),
    ([ROW + ["extra"]], COLUMNS, "number of fields"),
    ([ROW[:-1]], COLUMNS, "number of fields"),
    ([ROW, ROW], COLUMNS, "Duplicate order"),
    ([["SO-1", "2026-10-01", "Demo", "Support", "not money", "AUD"]], COLUMNS, "Sales row 2"),
])
def test_bad_csv_data(tmp_path, rows, header, message):
    with pytest.raises(ReportError, match=message):
        CsvExcelReader(csv_file(tmp_path, rows, header)).read()


@pytest.mark.parametrize("suffix,content,message", [
    (".csv", b'order_id,"unterminated', "malformed"),
    (".csv", b'\xff\xfe\x00', "encoding"),
    (".xlsx", b'not a zip', "damaged"),
    (".xls", b'old format', "Unsupported"),
])
def test_bad_files(tmp_path, suffix, content, message):
    path = tmp_path / ("broken" + suffix)
    path.write_bytes(content)
    with pytest.raises(ReportError, match=message):
        CsvExcelReader(path).read()


def test_missing_file_is_logged(tmp_path, caplog):
    with pytest.raises(ReportError, match="cannot read"):
        CsvExcelReader(tmp_path / "missing.csv").read()
    assert "cannot read" in caplog.text


def test_excel_requires_named_sheet(tmp_path):
    with pytest.raises(ReportError, match="worksheet"):
        CsvExcelReader(excel_file(tmp_path, [ROW], sheet="Other")).read()


@pytest.mark.parametrize("value", ["=5+5", "#DIV/0!"])
def test_excel_rejects_formulas_and_error_cells(tmp_path, value):
    row = list(ROW)
    row[4] = value
    with pytest.raises(ReportError, match="formulas or error"):
        CsvExcelReader(excel_file(tmp_path, [row])).read()


def test_excel_rejects_time_of_day(tmp_path):
    row = list(ROW)
    row[1] = datetime(2026, 10, 1, 12)
    with pytest.raises(ReportError, match="without a time"):
        CsvExcelReader(excel_file(tmp_path, [row])).read()


def test_duplicates_across_files_are_not_double_counted(tmp_path):
    data = CsvExcelReader(csv_file(tmp_path, [ROW])).read()
    with pytest.raises(ReportError, match="Duplicate order"):
        merge_sources(data, data)

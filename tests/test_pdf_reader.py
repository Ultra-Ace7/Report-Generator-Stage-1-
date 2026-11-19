from decimal import Decimal
from pathlib import Path

import pytest

from core.exceptions import ReportError
from sources.base import read_boundary
from sources.pdf_reader import PdfMetricsReader, parse_metrics_text

SAMPLES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
TEXT = """Reporting Month Sales Target (AUD)
2026-10 8000.00
2026-11 10000.00
Demo task snapshot benchmark
Completion Rate Target: 80%
Scope: demo_task_snapshot
"""


def test_actual_pdf_extraction():
    result = PdfMetricsReader(SAMPLES / "monthly_metrics.pdf").read()
    assert [t.sales_target for t in result.monthly_targets] == [Decimal("8000.00"), Decimal("10000.00")]
    assert str(result.monthly_targets[0].month) == "2026-10-01"
    assert result.benchmark.completion_rate_target == Decimal("0.8")


@pytest.mark.parametrize("text,message", [
    ("", "no extractable text"),
    ("unrelated document", "layout"),
    (TEXT.replace("8000.00", "bad"), "invalid month or amount"),
    (TEXT.replace("2026-10", "2026-13"), "invalid data"),
    (TEXT.replace("2026-11", "2026-10"), "one sales target"),
    (TEXT.replace("80%", "120%"), "invalid data"),
    (TEXT.replace("80%", "80"), "percentage"),
    (TEXT.replace("Scope: demo_task_snapshot", "Scope: monthly"), "scope"),
    (TEXT + "Completion Rate Target: 90%\n", "one completion benchmark"),
    (TEXT.replace("2026-10 8000.00\n2026-11 10000.00\n", ""), "empty"),
])
def test_bad_pdf_text_is_not_silently_ignored(text, message):
    with pytest.raises(ReportError, match=message):
        with read_boundary("PDF test"):
            parse_metrics_text(text)


def test_corrupt_pdf_logged(tmp_path, caplog):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"not a PDF")
    with pytest.raises(ReportError, match="Cannot read PDF"):
        PdfMetricsReader(path).read()
    assert "Cannot read PDF" in caplog.text


def test_missing_pdf(tmp_path):
    with pytest.raises(ReportError, match="cannot read input"):
        PdfMetricsReader(tmp_path / "missing.pdf").read()

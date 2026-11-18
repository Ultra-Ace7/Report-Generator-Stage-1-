"""Read the documented text-based monthly metrics PDF layout."""
import re
from decimal import Decimal
from pathlib import Path

import pdfplumber

from core.exceptions import DataValidationError, SourceReadError
from core.schemas import MonthlyTarget, SnapshotBenchmark
from sources.base import SourceData, read_boundary

HEADER = "Reporting Month Sales Target (AUD)"
BENCHMARK_HEADING = "Demo task snapshot benchmark"


def parse_metrics_text(text: str) -> SourceData:
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    if not lines:
        raise DataValidationError("PDF contains no extractable text. Scanned PDFs require OCR and are not supported.")
    if lines.count(HEADER) != 1 or lines.count(BENCHMARK_HEADING) != 1:
        raise DataValidationError("PDF does not match the documented monthly metrics layout.")
    start, end = lines.index(HEADER) + 1, lines.index(BENCHMARK_HEADING)
    if end <= start:
        raise DataValidationError("PDF sales target table is empty or misplaced.")
    targets = []
    for line in lines[start:end]:
        match = re.fullmatch(r"(\d{4}-\d{2}) ([0-9]+(?:\.[0-9]{1,2})?)", line)
        if not match:
            raise DataValidationError("PDF target table contains an invalid month or amount.")
        targets.append(MonthlyTarget(month=match[1] + "-01", sales_target=match[2]))
    rates = [line for line in lines[end + 1:] if line.startswith("Completion Rate Target:")]
    scopes = [line for line in lines[end + 1:] if line.startswith("Scope:")]
    if len(rates) != 1 or scopes != ["Scope: demo_task_snapshot"]:
        raise DataValidationError("PDF requires one completion benchmark with scope demo_task_snapshot.")
    rate = re.fullmatch(r"Completion Rate Target: ([0-9]+(?:\.[0-9]+)?)%", rates[0])
    if not rate:
        raise DataValidationError("PDF completion benchmark must be a percentage.")
    return SourceData(monthly_targets=targets, benchmark=SnapshotBenchmark(completion_rate_target=Decimal(rate[1]) / 100))


class PdfMetricsReader:
    def __init__(self, path):
        self.path = Path(path)

    def read(self) -> SourceData:
        with read_boundary("Metrics PDF {}".format(self.path.name)):
            if self.path.suffix.lower() != ".pdf":
                raise SourceReadError("Metrics input must be a .pdf file.")
            try:
                with pdfplumber.open(self.path) as document:
                    text = "\n".join(page.extract_text() or "" for page in document.pages)
            except OSError:
                raise
            except Exception as exc:
                raise SourceReadError("Cannot read PDF; it may be damaged, encrypted or unsupported.") from exc
            return parse_metrics_text(text)

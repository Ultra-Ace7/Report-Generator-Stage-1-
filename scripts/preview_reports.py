"""Preview report calculations and charts, before Word rendering is added."""
import argparse
import logging
from pathlib import Path
import sys

from pydantic import ValidationError

from core.exceptions import ReportError
from core.schemas import DateRange
from renderer.chart_builder import render_chart
from reports.operations_kpi import OperationsKpiBuilder
from reports.sales_summary import SalesSummaryBuilder
from sources.api_reader import OfflineTaskReader
from sources.base import merge_sources
from sources.csv_excel import CsvExcelReader
from sources.pdf_reader import PdfMetricsReader

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Preview reports using synthetic sales, metrics PDF and offline tasks; no DOCX yet.")
    parser.add_argument("--start", default="2026-10-01")
    parser.add_argument("--end", default="2026-10-31")
    args = parser.parse_args(argv)
    try:
        (ROOT / "logs").mkdir(exist_ok=True)
        logging.basicConfig(filename=str(ROOT / "logs" / "report_generator.log"), level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(name)s %(message)s")
        period = DateRange(start=args.start, end=args.end)
        samples = ROOT / "sample_data"
        from sources.task_files import TaskFilesReader
        data = merge_sources(CsvExcelReader(samples / 'Sales_Summary_Dummy_Data/sales_2026-10.csv').read(),
                             TaskFilesReader([samples / 'Operations_KPI_Dummy_Data/operations_tasks_2026-10.csv']).read())
        reports = [SalesSummaryBuilder().build(data, period), OperationsKpiBuilder().build(data, period)]
        rendered = [(report, render_chart(report.chart)) for report in reports]
        output = ROOT / "output" / "preview"
        output.mkdir(parents=True, exist_ok=True)
        for report, chart in rendered:
            name = "{}_{}_{}".format(report.report_type, period.start, period.end)
            (output / (name + ".json")).write_text(report.model_dump_json(indent=2), encoding="utf-8")
            (output / (name + ".png")).write_bytes(chart)
            print("\n{}\n{}".format(report.title, report.summary))
            for metric in report.metrics:
                print("  {}: {}".format(metric.label, metric.display))
        print("\nPreview JSON and PNG files saved to {}. No Word reports generated yet.".format(output))
        return 0
    except (ReportError, ValidationError, OSError) as exc:
        logging.getLogger("report_generator.reports").error("Report preview failed: %s", exc)
        print("Report preview failed: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

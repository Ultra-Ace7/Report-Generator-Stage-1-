"""Run `python -m scripts.check_sources` to validate the sample inputs."""
import argparse
import logging
import sys
from pathlib import Path

from core.exceptions import ReportError
from sources.api_reader import ApiTaskReader, OfflineTaskReader
from sources.base import merge_sources
from sources.csv_excel import CsvExcelReader
from sources.pdf_reader import PdfMetricsReader

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check sample data readers; this does not generate a report.")
    parser.add_argument("--live-api", action="store_true", help="Fetch JSONPlaceholder instead of using the explicit offline fixture")
    args = parser.parse_args(argv)
    samples = ROOT / "sample_data"
    try:
        log_dir = ROOT / "logs"
        log_dir.mkdir(exist_ok=True)
        logging.basicConfig(
            filename=str(log_dir / "report_generator.log"), level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        api = ApiTaskReader() if args.live_api else OfflineTaskReader(
            samples / "todos_fixture.json", samples / "todos_fixture_metadata.json",
        )
        data = merge_sources(
            CsvExcelReader(samples / "sales.csv").read(),
            PdfMetricsReader(samples / "monthly_metrics.pdf").read(),
            api.read(),
        )
    except (ReportError, OSError) as exc:
        print("Source check failed: {}".format(exc), file=sys.stderr)
        return 1
    print("Sales orders: {} | Monthly targets: {}".format(len(data.orders), len(data.monthly_targets)))
    print("Task snapshot: {} | Tasks: {} | Completed: {}".format(
        data.snapshot.mode, len(data.snapshot.tasks), sum(task.completed for task in data.snapshot.tasks),
    ))
    print("Snapshot timestamp: {}".format(data.snapshot.captured_at.isoformat()))
    print("All selected sources validated. No report has been generated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

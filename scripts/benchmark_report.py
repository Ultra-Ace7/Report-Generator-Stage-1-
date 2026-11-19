"""Opt-in synthetic end-to-end benchmark; results are machine-specific observations."""
import argparse
import csv
import json
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

from docx import Document
from core.report_service import ReportService
from core.schemas import DateRange
from sources.csv_excel import COLUMNS, CsvExcelReader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', type=int, default=1000)
    args = parser.parse_args()
    if not 1 <= args.rows <= 10000:
        parser.error('--rows must be between 1 and 10000')
    with TemporaryDirectory(prefix='report-benchmark-') as directory:
        path = Path(directory)
        source = path / 'sales.csv'
        with source.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(COLUMNS)
            writer.writerows((str(i), '2026-10-15', 'Synthetic Customer', 'Support', '1.00', 'AUD') for i in range(args.rows))
        started = perf_counter()
        result = ReportService().generate('sales_summary', DateRange(start='2026-10-01', end='2026-10-31'),
                                          [CsvExcelReader(source)], path / 'report.docx')
        seconds = perf_counter() - started
        doc = Document(result.path)
        actual = len(doc.tables[1].rows) - 1
        if actual != args.rows or result.content.metrics[0].value != args.rows:
            raise RuntimeError('Generated report failed row count or revenue verification.')
        peak = None
        if sys.platform in ('darwin', 'linux'):
            import resource
            raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            peak = round(raw / (1024 * 1024 if sys.platform == 'darwin' else 1024), 2)
        print(json.dumps({'rows': actual, 'input_bytes': source.stat().st_size,
            'docx_bytes': result.path.stat().st_size, 'generation_seconds': round(seconds, 3),
            'process_peak_rss_mib': peak, 'platform': platform.system(), 'python': platform.python_version(),
            'scope': 'One process; RSS includes imports and verification. Not a concurrency test or memory-leak proof.'}, indent=2))


if __name__ == '__main__':
    main()

"""Generate two offline demonstration reports from the same company template."""
import argparse
from datetime import datetime
import logging
from pathlib import Path
import sys

from core.exceptions import ReportError
from core.schemas import DateRange
from core.input_selection import build_readers
from core.report_service import ReportService

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description='Generate two offline sample DOCX reports.')
    parser.add_argument('--output-dir', type=Path, default=None)
    args = parser.parse_args(argv)
    output = args.output_dir or ROOT / 'output' / ('samples_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    try:
        (ROOT / 'logs').mkdir(exist_ok=True)
        logging.basicConfig(filename=str(ROOT / 'logs' / 'report_generator.log'), level=logging.INFO,
                            format='%(asctime)s %(levelname)s %(name)s %(message)s')
        sample = ROOT / 'sample_data'
        readers = build_readers([sample / 'sales.csv'], sample / 'monthly_metrics.pdf', 'offline')
        period = DateRange(start='2026-10-01', end='2026-10-31')
        service = ReportService(ROOT / 'templates' / 'company_template.docx')
        for report_type, name in (('sales_summary', 'SalesSummary'), ('operations_kpi', 'OperationsKPI')):
            result = service.generate(report_type, period, readers, output / (name + '_2026-10_offline_demo.docx'))
            print(result.path)
        return 0
    except (ReportError, OSError) as exc:
        print('Sample generation failed: {}'.format(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

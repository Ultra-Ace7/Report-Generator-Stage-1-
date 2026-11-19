"""Non-interactive report generation, ready for a future scheduler."""
import argparse
import logging
from pathlib import Path
import sys

from pydantic import ValidationError

from core.exceptions import ReportError
from core.input_selection import build_readers
from sources.api_reader import TODOS_URL
from core.logging_config import configure_logging
from core.report_service import DEFAULT_TEMPLATE, REPORT_LABELS, ReportService
from core.schemas import DateRange


def main(argv=None):
    parser = argparse.ArgumentParser(description='TechInnovate Report Generator')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0')
    parser.add_argument('--report', required=True, choices=tuple(REPORT_LABELS))
    parser.add_argument('--start', required=True, help='Inclusive sales start date, YYYY-MM-DD')
    parser.add_argument('--end', required=True, help='Inclusive sales end date, YYYY-MM-DD')
    parser.add_argument('--sales', type=Path, action='append', default=[], help='CSV/XLSX path; repeat for multiple files')
    parser.add_argument('--sheet', default='Sales', help='Excel worksheet name (default: Sales)')
    parser.add_argument('--metrics', type=Path, help='Optional monthly metrics PDF')
    parser.add_argument('--tasks', choices=('none', 'offline', 'live'), default='none', help='Explicit task snapshot mode (default: none)')
    parser.add_argument('--task-api-url', default=TODOS_URL, help='Public HTTPS task API URL (used with --tasks live)')
    parser.add_argument('--sales-api-url', help='Compatible public HTTPS sales order JSON endpoint')
    parser.add_argument('--template', type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument('--output', type=Path, required=True, help='New .docx output path; existing files are never overwritten')
    args = parser.parse_args(argv)
    try:
        configure_logging()
        period = DateRange(start=args.start, end=args.end)
        result = ReportService(args.template).generate(args.report, period,
            build_readers(args.sales, args.metrics, args.tasks, args.sheet, api_url=args.task_api_url, sales_api_url=args.sales_api_url), args.output)
    except ValidationError as exc:
        message = '; '.join(e['msg'] for e in exc.errors(include_input=False, include_url=False))
        logging.getLogger('report_generator.cli').error('Invalid date range: %s', message)
        print('Report generation failed: {}'.format(message), file=sys.stderr)
        return 1
    except (ReportError, OSError) as exc:
        logging.getLogger('report_generator.cli').error('Report generation failed: %s', exc)
        print('Report generation failed: {}'.format(exc), file=sys.stderr)
        return 1
    print('Report saved: {}'.format(result.path.resolve()))
    return 0


if __name__ == '__main__':
    sys.exit(main())

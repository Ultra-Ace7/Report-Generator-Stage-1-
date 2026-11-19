"""The single generation pipeline used by both UI and command line."""
from dataclasses import dataclass
import logging
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from sources.sales_api import ApiSalesReader
from typing import Mapping, Optional, Sequence

from pydantic import ValidationError

from core.exceptions import DataValidationError, ReportError
from core.schemas import DateRange
from renderer.word_renderer import WordRenderer
from reports.base import ReportBuilder, ReportData
from reports.operations_kpi import OperationsKpiBuilder
from reports.sales_summary import SalesSummaryBuilder
from sources.base import DataReader, merge_sources

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / 'templates' / 'company_template.docx'
REPORT_LABELS = {'sales_summary': 'Sales Summary', 'operations_kpi': 'Operations / KPI Report'}
DEFAULT_BUILDERS = {'sales_summary': SalesSummaryBuilder(), 'operations_kpi': OperationsKpiBuilder()}
logger = logging.getLogger('report_generator.service')


@dataclass(frozen=True)
class GeneratedReport:
    content: ReportData
    path: Path


class ReportService:
    def __init__(self, template_path=DEFAULT_TEMPLATE, builders: Optional[Mapping[str, ReportBuilder]] = None):
        self.renderer = WordRenderer(template_path)
        self.builders = dict(DEFAULT_BUILDERS if builders is None else builders)

    def generate(self, report_type: str, period: DateRange, readers: Sequence[DataReader], output_path) -> GeneratedReport:
        try:
            if report_type not in self.builders:
                raise DataValidationError('Choose a supported report type.')
            if not readers:
                raise DataValidationError('Select at least one data source.')
            data = merge_sources(*(reader.read() for reader in readers))
            if report_type == 'sales_summary' and not data.orders:
                raise DataValidationError('Sales Summary requires sales data containing orders and revenue. Target-only PDFs and task APIs do not contain sales orders; supply a sales CSV/Excel, sales-table PDF or Sales orders API.')
            content = self.builders[report_type].build(data, period)
            api_notes = []
            for reader in readers:
                if isinstance(reader, ApiSalesReader):
                    parts = urlsplit(reader.url)
                    source = urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))
                    api_notes.append('Sales API source: {} (query omitted). Values are supplied by the endpoint; transaction dates and AUD currency are validated, not independently audited. No missing sales facts are inferred.'.format(source))
            if api_notes:
                content = content.model_copy(update={'notes': content.notes + tuple(api_notes)})
            path = self.renderer.render(content, output_path)
            logger.info('Report generated: type=%s start=%s end=%s', report_type, period.start, period.end)
            return GeneratedReport(content=content, path=path)
        except ReportError as exc:
            logger.error('Report generation failed: %s', exc)
            raise
        except (ValidationError, OSError) as exc:
            logger.error('Invalid report input or inaccessible file: %s', type(exc).__name__)
            raise DataValidationError('Report input is invalid or a required file is inaccessible. Check the selected inputs.') from exc
        except Exception as exc:
            logger.exception('Unexpected report generation failure')
            raise ReportError('An unexpected error prevented report generation. See logs/report_generator.log for details.') from exc

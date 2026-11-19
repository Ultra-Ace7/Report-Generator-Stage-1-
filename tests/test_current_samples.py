"""Integration tests for the user's current editable demonstration files."""
from decimal import Decimal
from datetime import datetime
from uuid import uuid4
from pathlib import Path
from docx import Document
import pytest
from core.report_service import ReportService,DEFAULT_TEMPLATE
from core.schemas import DateRange
from sources.csv_excel import CsvExcelReader
from sources.pdf_reader import PdfInputReader
from sources.task_files import TaskFilesReader

ROOT=Path(__file__).resolve().parents[1]
SALES=ROOT/'sample_data/Sales_Summary_Dummy_Data'
TASKS=ROOT/'sample_data/Operations_KPI_Dummy_Data'
PERIOD=DateRange(start='2026-10-01',end='2026-11-30')
SALES_CASES=[('sales_2026-10.csv','7390.00'),('sales_2026-10.xlsx','7390.00'),('Sales_2026_10-11.pdf','7390.00'),('sales_2026-11.csv','8650.00'),('sales_2026-11.xlsx','8650.00')]
TASK_CASES=[('operations_tasks_2026-10.csv',12,9),('sameid_tasks_2026-10.xlsx',12,9),('sameid_tasks_2026-10.pdf',12,9),('operations_tasks_2026-11.csv',10,7),('operations_tasks_2026-11.xlsx',10,7),('operations_tasks_2026-11.pdf',10,7)]


@pytest.fixture(scope='module')
def sample_report_run():
    return datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid4().hex[:8]


def retained_report(category, run, source_name):
    source = Path(source_name)
    return ROOT/'sample_reports'/category/run/('{}_from_{}.docx'.format(source.stem, source.suffix[1:]))


@pytest.mark.parametrize('name,total',SALES_CASES)
def test_current_sales_to_word(sample_report_run,name,total):
    path=SALES/name
    reader=PdfInputReader(path) if path.suffix=='.pdf' else CsvExcelReader(path,sheet_name=None)
    before=DEFAULT_TEMPLATE.read_bytes()
    result=ReportService().generate('sales_summary',PERIOD,[reader],retained_report('Sales_Summary',sample_report_run,name))
    values={metric.key:metric.value for metric in result.content.metrics}
    assert values['total_orders']==5 and values['total_revenue']==Decimal(total)
    assert values['average_order_value']==Decimal(total)/5
    document=Document(result.path)
    assert len(document.inline_shapes)==1 and len(document.tables[1].rows)==6
    assert DEFAULT_TEMPLATE.read_bytes()==before


@pytest.mark.parametrize('name,count,completed',TASK_CASES)
def test_current_tasks_to_word(sample_report_run,name,count,completed):
    before=DEFAULT_TEMPLATE.read_bytes()
    result=ReportService().generate('operations_kpi',PERIOD,[TaskFilesReader([TASKS/name])],retained_report('Operations_KPI',sample_report_run,name))
    values={metric.key:metric.value for metric in result.content.metrics}
    assert values['total_tasks']==count and values['completed_tasks']==completed
    assert values['completion_rate']==Decimal(completed)/count*100
    document=Document(result.path)
    assert len(document.inline_shapes)==1 and len(document.tables[-1].rows)==count+1
    assert [cell.text for cell in document.tables[-1].rows[0].cells]==['Task ID','Task Name','User ID','Status','Created']
    assert DEFAULT_TEMPLATE.read_bytes()==before

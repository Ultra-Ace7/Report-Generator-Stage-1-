"""Translate entry-point selections into source adapters, not report logic."""
from pathlib import Path

from core.exceptions import DataValidationError
from sources.api_reader import ApiTaskReader, OfflineTaskReader, TODOS_URL
from sources.task_files import TaskFilesReader
from sources.sales_api import ApiSalesReader
from sources.csv_excel import CsvExcelReader
from sources.pdf_reader import PdfInputReader

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / 'sample_data'
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def build_readers(sales_files=(), metrics_file=None, task_mode='none', sheet_name='Sales', api_url=TODOS_URL, sales_api_url=None, task_files=()):
    readers = [CsvExcelReader(path, sheet_name=sheet_name) for path in sales_files]
    if metrics_file is not None:
        readers.append(PdfInputReader(metrics_file))
    if task_files:
        readers.append(TaskFilesReader(task_files, sheet_name=sheet_name))
    if task_mode == 'offline':
        readers.append(OfflineTaskReader(SAMPLES / 'todos_fixture.json', SAMPLES / 'todos_fixture_metadata.json'))
    elif task_mode == 'live':
        readers.append(ApiTaskReader(url=api_url))
    elif task_mode != 'none':
        raise DataValidationError('Select a valid task source: none, offline or live.')
    if sales_api_url is not None:
        readers.append(ApiSalesReader(url=sales_api_url))
    return readers


def save_upload(upload, directory, stem, allowed_suffixes):
    """Use generated filenames so uploaded names never become filesystem paths."""
    suffix = Path(upload.name).suffix.lower()
    if suffix not in allowed_suffixes:
        raise DataValidationError('Unsupported uploaded file type: use {}.'.format(', '.join(allowed_suffixes)))
    data = upload.getvalue()
    if not data:
        raise DataValidationError('Uploaded file is empty.')
    if len(data) > MAX_UPLOAD_BYTES:
        raise DataValidationError('Each uploaded file must be 20 MB or smaller.')
    path = Path(directory) / (stem + suffix)
    path.write_bytes(data)
    return path


def save_uploads(uploads, directory):
    """Route files by suffix; readers validate their contents before reporting."""
    if sum(Path(upload.name).suffix.lower() == '.pdf' for upload in uploads) > 1:
        raise DataValidationError('Supply at most one PDF metrics file; multiple PDFs are ambiguous.')
    sales_files, metrics_file = [], None
    for index, upload in enumerate(uploads):
        path = save_upload(upload, directory, 'input_{}'.format(index), ('.csv', '.xlsx', '.pdf'))
        if path.suffix == '.pdf':
            metrics_file = path
        else:
            sales_files.append(path)
    return sales_files, metrics_file

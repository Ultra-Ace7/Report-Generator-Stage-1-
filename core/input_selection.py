"""Translate entry-point selections into source adapters, not report logic."""
from pathlib import Path

from core.exceptions import DataValidationError
from sources.api_reader import ApiTaskReader, OfflineTaskReader
from sources.csv_excel import CsvExcelReader
from sources.pdf_reader import PdfMetricsReader

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / 'sample_data'
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def build_readers(sales_files=(), metrics_file=None, task_mode='none', sheet_name='Sales'):
    readers = [CsvExcelReader(path, sheet_name=sheet_name) for path in sales_files]
    if metrics_file is not None:
        readers.append(PdfMetricsReader(metrics_file))
    if task_mode == 'offline':
        readers.append(OfflineTaskReader(SAMPLES / 'todos_fixture.json', SAMPLES / 'todos_fixture_metadata.json'))
    elif task_mode == 'live':
        readers.append(ApiTaskReader())
    elif task_mode != 'none':
        raise DataValidationError('Select a valid task source: none, offline or live.')
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

"""Stable regression fixtures; current demo-data integration is tested separately."""
from pathlib import Path
from core.input_selection import build_readers as application_readers
from sources.api_reader import OfflineTaskReader
ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(__file__).resolve().parent / 'fixtures'


def build_readers(sales_files=(), metrics_file=None, task_mode='none', sheet_name='Sales', **kwargs):
    readers = application_readers(sales_files, metrics_file, 'none' if task_mode == 'offline' else task_mode, sheet_name, **kwargs)
    if task_mode == 'offline':
        readers.append(OfflineTaskReader(SAMPLES/'todos_fixture.json', SAMPLES/'todos_fixture_metadata.json'))
    return readers

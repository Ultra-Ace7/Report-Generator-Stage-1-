"""Explicit task tables from CSV, XLSX and bordered text PDFs."""
import csv
from datetime import datetime, timezone
from pathlib import Path
import re
import pdfplumber
from openpyxl import load_workbook
from core.exceptions import DataValidationError, SourceReadError
from core.schemas import TaskSnapshot, Task
from sources.api_reader import normalize_tasks
from sources.base import SourceData, read_boundary

FIELDS = ('Task ID', 'Task Name', 'User ID', 'Status', 'Created')
LEGACY_FIELDS = ('userId', 'id', 'title', 'completed')


def key(value):
    return re.sub(r'[\s_-]+', '', str(value or '')).casefold()


def task_rows(rows):
    rows = iter(rows)
    header = next(rows, [])
    mapping = {key(field): field for field in FIELDS}
    names = [mapping.get(key(cell)) for cell in header]
    modern = len(names) == 5 and set(names) == set(FIELDS)
    if not modern:
        mapping = {key(field): field for field in LEGACY_FIELDS}
        names = [mapping.get(key(cell)) for cell in header]
        if len(names) != 4 or set(names) != set(LEGACY_FIELDS):
            raise DataValidationError('Task table requires Task ID, Task Name, User ID, Status and Created exactly once.')
    records = []
    for number, row in enumerate(rows, 2):
        if not row or all(value is None or str(value).strip() == '' for value in row):
            continue
        if [key(cell) for cell in row] == [key(cell) for cell in header]:
            continue
        with read_boundary('Task row {}'.format(number)):
            if len(row) != len(names):
                raise DataValidationError('Task row has an unexpected number of fields.')
            record = dict(zip(names, row))
            if modern:
                raw = record
                status = str(raw['Status']).strip().casefold()
                if status not in ('completed', 'pending'):
                    raise DataValidationError('Status must be Completed or Pending.')
                created = raw['Created']
                if isinstance(created, datetime):
                    if created.time() != datetime.min.time() or created.tzinfo is not None:
                        raise DataValidationError('Created must be a date without a time.')
                    created = created.date()
                if isinstance(created, str) and re.fullmatch(r'\d{4}/\d{1,2}/\d{1,2}', created.strip()):
                    y, m, d = map(int, created.strip().split('/'))
                    created = '{:04d}-{:02d}-{:02d}'.format(y, m, d)
                if created is None or created == '':
                    raise DataValidationError('Created is required; use YYYY-MM-DD.')
                record = dict(userId=raw['User ID'], id=raw['Task ID'], title=raw['Task Name'], completed=status == 'completed')
            for field in ('userId', 'id'):
                value = record[field]
                if isinstance(value, str) and re.fullmatch(r'[0-9]+', value.strip()):
                    record[field] = int(value.strip())
            value = record['completed']
            if isinstance(value, str) and value.strip().lower() in ('true', 'false'):
                record['completed'] = value.strip().lower() == 'true'
            task = normalize_tasks([record])[0]
            if modern:
                task = Task(task_id=task.task_id, user_id=task.user_id, title=task.title, completed=task.completed, created=created)
            records.append(task)
    if not records:
        raise DataValidationError('Task table contains no task records.')
    return records


class TaskFilesReader:
    def __init__(self, paths, sheet_name=None):
        self.paths = [Path(path) for path in paths]
        self.sheet_name = sheet_name

    def read(self) -> SourceData:
        tasks = []
        for path in self.paths:
            with read_boundary('Task file {}'.format(path.name)):
                if path.suffix.lower() == '.csv':
                    try:
                        with path.open(encoding='utf-8-sig', newline='') as stream:
                            tasks.extend(task_rows(csv.reader(stream, strict=True)))
                    except csv.Error as exc:
                        raise SourceReadError('Malformed task CSV.') from exc
                elif path.suffix.lower() == '.xlsx':
                    try:
                        book = load_workbook(path, read_only=True, data_only=False)
                    except Exception as exc:
                        raise SourceReadError('Cannot open task Excel workbook.') from exc
                    try:
                        name = self.sheet_name or book.sheetnames[0]
                        if name not in book.sheetnames:
                            raise DataValidationError("Excel worksheet '{}' was not found.".format(name))
                        cells = list(book[name].iter_rows())
                        if any(cell.data_type in ('f', 'e') for row in cells for cell in row):
                            raise DataValidationError('Task Excel must contain values, not formulas or error cells.')
                        tasks.extend(task_rows([[cell.value for cell in row] for row in cells]))
                    finally:
                        book.close()
                elif path.suffix.lower() == '.pdf':
                    try:
                        with pdfplumber.open(path) as doc:
                            tables = [table for page in doc.pages for table in page.extract_tables()]
                    except Exception as exc:
                        raise SourceReadError('Cannot read task PDF.') from exc
                    if not tables:
                        raise DataValidationError('Task PDF requires a text-based table with visible cell borders and Task ID, Task Name, User ID, Status, Created headers.')
                    for table in tables:
                        tasks.extend(task_rows(table))
                else:
                    raise DataValidationError('Task files must be CSV, XLSX or PDF.')
        with read_boundary('Combined task files'):
            return SourceData(snapshot=TaskSnapshot(tasks=tasks, captured_at=datetime.now(timezone.utc),
                source='Uploaded task files: ' + ', '.join(path.name for path in self.paths), mode='uploaded_files'))

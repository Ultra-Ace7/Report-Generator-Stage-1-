"""Sales input adapter for UTF-8 CSV and .xlsx files."""
import csv
from datetime import datetime, time
from pathlib import Path

from openpyxl import load_workbook

from core.exceptions import DataValidationError, SourceReadError
from core.schemas import SalesOrder
from sources.base import SourceData, read_boundary

from sources.sales_fields import COLUMNS, map_sales_header


def normalize_rows(rows):
    """Preserve text/money exactly; validate every nonblank row."""
    rows = iter(rows)
    header = next(rows, None)
    if header is None:
        raise DataValidationError("Sales input is empty.")
    names = map_sales_header(header)
    orders = []
    for number, row in enumerate(rows, 2):
        if not row or all(value is None or (isinstance(value, str) and not value.strip()) for value in row):
            continue
        if len(row) != len(names):
            raise DataValidationError("Sales row {} has an unexpected number of fields.".format(number))
        record = {name: value for name, value in zip(names, row) if name is not None}
        value = record["order_date"]
        if isinstance(value, datetime):
            if value.time() != time.min or value.tzinfo is not None:
                raise DataValidationError("Sales row {} column order_date must use a date without a time.".format(number))
            record["order_date"] = value.date()
        # A nested boundary retains the physical input row in validation errors.
        with read_boundary("Sales row {}".format(number)):
            orders.append(SalesOrder.model_validate(record))
    if not orders:
        raise DataValidationError("Sales input contains no orders.")
    return SourceData(orders=orders)


class CsvExcelReader:
    def __init__(self, path, sheet_name="Sales"):
        self.path = Path(path)
        self.sheet_name = sheet_name

    def read(self) -> SourceData:
        with read_boundary("Sales file {}".format(self.path.name)):
            suffix = self.path.suffix.lower()
            if suffix == ".csv":
                try:
                    with self.path.open(encoding="utf-8-sig", newline="") as stream:
                        return normalize_rows(csv.reader(stream, strict=True))
                except csv.Error as exc:
                    raise SourceReadError("CSV is malformed; check quoting and delimiters.") from exc
            if suffix == ".xlsx":
                return self._read_excel()
            raise SourceReadError("Unsupported sales file type. Use .csv or .xlsx.")

    def _read_excel(self):
        # Keep parser failures separate from validation/programming errors.
        try:
            workbook = load_workbook(self.path, read_only=True, data_only=False)
        except OSError:
            raise
        except Exception as exc:
            raise SourceReadError("Cannot open Excel workbook; it may be damaged or encrypted.") from exc
        try:
            sheet_name = self.sheet_name or workbook.sheetnames[0]
            if sheet_name not in workbook.sheetnames:
                raise DataValidationError("Excel worksheet '{}' was not found.".format(self.sheet_name))
            try:
                rows = list(workbook[sheet_name].iter_rows())
            except Exception as exc:
                raise SourceReadError("Cannot read Excel worksheet; the file may be damaged.") from exc
            for row in rows:
                if any(cell.data_type in ("f", "e") for cell in row):
                    raise DataValidationError("Excel input must contain values, not formulas or error cells.")
            return normalize_rows([tuple(cell.value for cell in row) for row in rows])
        finally:
            workbook.close()

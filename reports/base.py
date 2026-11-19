"""Report content contract, independent of file readers and document rendering."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, Optional, Protocol, Tuple

from pydantic import Field, model_validator

from core.schemas import DateRange, Record, SourceData


class Metric(Record):
    key: str
    label: str
    value: Optional[Decimal]
    unit: Literal["AUD", "count", "percent", "percentage_points"]
    unavailable_reason: Optional[str] = None

    @property
    def display(self) -> str:
        if self.value is None:
            return "Unavailable"
        if self.unit == "AUD":
            return money(self.value)
        if self.unit == "count":
            return "{:.0f}".format(self.value)
        suffix = "%" if self.unit == "percent" else " pp"
        return "{}{}".format(round_decimal(self.value, "0.1"), suffix)


class ReportTable(Record):
    title: str
    columns: Tuple[str, ...]
    rows: Tuple[Tuple[str, ...], ...]

    @model_validator(mode="after")
    def matching_columns(self):
        if not self.columns or any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("Table rows must match the column count.")
        return self


class ChartSpec(Record):
    kind: Literal["sales_trend", "task_status"]
    title: str
    labels: Tuple[str, ...]
    values: Tuple[Decimal, ...]
    y_label: str
    caption: str

    @model_validator(mode="after")
    def valid_points(self):
        if not self.labels or len(self.labels) != len(self.values):
            raise ValueError("Chart labels and values must have equal nonzero length.")
        if any(not value.is_finite() or value < 0 for value in self.values):
            raise ValueError("Chart values must be finite and nonnegative.")
        return self


class ReportData(Record):
    report_type: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    title: str
    requested_period: DateRange
    period_label: str
    metrics: Tuple[Metric, ...]
    summary: str
    notes: Tuple[str, ...]
    tables: Tuple[ReportTable, ...]
    chart: ChartSpec


class ReportBuilder(Protocol):
    def build(self, data: SourceData, period: DateRange) -> ReportData:
        ...


def round_decimal(value: Decimal, places: str) -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def money(value: Decimal) -> str:
    return "AUD {:,.2f}".format(round_decimal(value, "0.01"))


def snapshot_notes(snapshot) -> Tuple[str, ...]:
    return (
        "Task snapshot mode: {}. Snapshot timestamp: {}.".format(snapshot.mode, snapshot.captured_at.isoformat()),
        "Task source: {}.".format(snapshot.source),
        "Tasks are supplied snapshot records; Created, when supplied, is a creation date and not a completion date; the requested sales date range does not filter them. They are not linked to sales customers.",
    )

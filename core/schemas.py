"""Format-independent validated business data (Python 3.9 compatible)."""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator


def parse_date(value):
    """Accept calendar dates and ISO date strings, never timestamps or epochs."""
    if type(value) is date:
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value)
    raise ValueError("Use a calendar date in YYYY-MM-DD format.")


def parse_decimal(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("Use a finite decimal number.")
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Use a decimal number without currency symbols or separators.")
    if not result.is_finite():
        raise ValueError("Number must be finite.")
    return result


def parse_money(value):
    result = parse_decimal(value)
    if result < 0 or result > Decimal("999999999999.99"):
        raise ValueError("Money must be between 0 and 999999999999.99 AUD.")
    if result != result.quantize(Decimal("0.01")):
        raise ValueError("Money must have no more than two decimal places.")
    return result.quantize(Decimal("0.01"))


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class DateRange(Record):
    start: date
    end: date

    _dates = field_validator("start", "end", mode="before")(parse_date)

    @model_validator(mode="after")
    def chronological(self):
        if self.start > self.end:
            raise ValueError("Start date must be on or before end date.")
        return self

    def contains(self, value: date) -> bool:
        return self.start <= value <= self.end


class SalesOrder(Record):
    order_id: str = Field(min_length=1)
    order_date: date
    customer: str = Field(min_length=1)
    service: str = Field(min_length=1)
    revenue: Decimal
    currency: Literal["AUD"] = "AUD"

    _date = field_validator("order_date", mode="before")(parse_date)
    _money = field_validator("revenue", mode="before")(parse_money)


class MonthlyTarget(Record):
    # Month is represented by its first calendar day.
    month: date
    sales_target: Decimal = Field(gt=0)
    currency: Literal["AUD"] = "AUD"

    _date = field_validator("month", mode="before")(parse_date)
    _money = field_validator("sales_target", mode="before")(parse_money)

    @field_validator("month")
    @classmethod
    def first_day(cls, value):
        if value.day != 1:
            raise ValueError("Reporting month must use its first day.")
        return value


class Task(Record):
    # JSONPlaceholder field names are mapped by the API reader in Step 3.
    task_id: int = Field(strict=True, gt=0)
    user_id: int = Field(strict=True, gt=0)
    title: str = Field(min_length=1)
    completed: StrictBool


class TaskSnapshot(Record):
    tasks: Tuple[Task, ...] = Field(min_length=1)
    captured_at: datetime
    source: str = Field(min_length=1)
    mode: Literal["live_demo", "offline_fixture"]

    @field_validator("captured_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Snapshot timestamp must include a timezone.")
        return value

    @model_validator(mode="after")
    def unique_tasks(self):
        ids = [task.task_id for task in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate task IDs are not allowed.")
        return self


class SnapshotBenchmark(Record):
    """A demo snapshot benchmark, explicitly not a monthly activity target."""
    completion_rate_target: Decimal = Field(ge=0, le=1)
    scope: Literal["demo_task_snapshot"] = "demo_task_snapshot"

    _rate = field_validator("completion_rate_target", mode="before")(parse_decimal)


class BusinessData(Record):
    orders: Tuple[SalesOrder, ...] = ()
    monthly_targets: Tuple[MonthlyTarget, ...] = ()

    @model_validator(mode="after")
    def unique_keys(self):
        ids = [order.order_id for order in self.orders]
        months = [target.month for target in self.monthly_targets]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate order IDs are not allowed, including across files.")
        if len(months) != len(set(months)):
            raise ValueError("Only one sales target per month is allowed.")
        return self


class SourceData(BusinessData):
    """Normalized input shared by readers and report builders."""
    snapshot: Optional[TaskSnapshot] = None
    benchmark: Optional[SnapshotBenchmark] = None

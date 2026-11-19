from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from core.schemas import BusinessData, DateRange, MonthlyTarget, SalesOrder, SnapshotBenchmark, Task, TaskSnapshot


def order(**changes):
    values = dict(order_id="SO-1", order_date="2026-10-01", customer="Demo Co", service="Support", revenue="10.10")
    values.update(changes)
    return SalesOrder(**values)


def test_money_is_exact_and_text_is_trimmed():
    assert order(customer=" Demo Co ").customer == "Demo Co"
    assert order().revenue + order(revenue="0.20").revenue == Decimal("10.30")
    assert order(revenue="0").revenue == Decimal("0.00")


@pytest.mark.parametrize("value", ["-1", "1.001", "NaN", "Infinity", "1,000.00", "AUD 5", True, None, "1e100"])
def test_invalid_money(value):
    with pytest.raises(ValidationError):
        order(revenue=value)


@pytest.mark.parametrize("changes", [
    {"customer": " "}, {"order_id": ""}, {"service": " "}, {"currency": "USD"},
    {"order_date": "2026-02-30"}, {"order_date": "01/10/2026"},
    {"order_date": "2026-10-01T00:00:00"}, {"order_date": 1790812800},
    {"unknown": "unexpected"},
])
def test_invalid_order(changes):
    with pytest.raises(ValidationError):
        order(**changes)


def test_missing_required_field():
    with pytest.raises(ValidationError):
        SalesOrder(order_id="SO-1")


def test_range_rejects_reverse_and_includes_both_edges():
    with pytest.raises(ValidationError):
        DateRange(start="2026-11-02", end="2026-11-01")
    period = DateRange(start="2026-10-01", end="2026-10-31")
    assert period.contains(date(2026, 10, 1))
    assert period.contains(date(2026, 10, 31))
    assert not period.contains(date(2026, 11, 1))


def test_duplicates_across_combined_sources_are_rejected():
    with pytest.raises(ValidationError, match="Duplicate order"):
        BusinessData(orders=[order(), order(revenue="20")])
    target = MonthlyTarget(month="2026-10-01", sales_target="100")
    with pytest.raises(ValidationError, match="one sales target"):
        BusinessData(monthly_targets=[target, target])


@pytest.mark.parametrize("changes", [{"month": "2026-10-02"}, {"sales_target": "0"}, {"sales_target": "-1"}])
def test_invalid_target(changes):
    values = dict(month="2026-10-01", sales_target="100")
    values.update(changes)
    with pytest.raises(ValidationError):
        MonthlyTarget(**values)


@pytest.mark.parametrize("value", ["true", "false", 0, 1, None])
def test_task_completion_is_a_real_boolean(value):
    with pytest.raises(ValidationError):
        Task(task_id=1, user_id=1, title="Demo", completed=value)


@pytest.mark.parametrize("value", [True, "1", 0, -1])
def test_task_id_is_a_positive_integer(value):
    with pytest.raises(ValidationError):
        Task(task_id=value, user_id=1, title="Demo", completed=True)


def test_snapshot_provenance_and_uniqueness():
    task = Task(task_id=1, user_id=1, title="Demo", completed=True)
    fields = dict(tasks=[task], captured_at="2026-11-17T09:00:00+11:00", source="Synthetic demo", mode="offline_fixture")
    assert TaskSnapshot(**fields).captured_at.utcoffset() is not None
    for changes in ({"captured_at": "2026-11-17T09:00:00"}, {"tasks": []}, {"tasks": [task, task]}, {"mode": "historical"}):
        with pytest.raises(ValidationError):
            TaskSnapshot(**dict(fields, **changes))


@pytest.mark.parametrize("value", ["-0.1", "1.1", "NaN", True])
def test_invalid_snapshot_benchmark(value):
    with pytest.raises(ValidationError):
        SnapshotBenchmark(completion_rate_target=value)

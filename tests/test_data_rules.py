from decimal import Decimal

import pytest

from core.data_rules import select_orders, target_coverage
from core.exceptions import DataValidationError
from core.schemas import BusinessData, DateRange, MonthlyTarget, SalesOrder


def data(months=("2026-10-01", "2026-11-01")):
    return BusinessData(monthly_targets=[MonthlyTarget(month=m, sales_target="100.00") for m in months])


@pytest.mark.parametrize("start,end,total", [
    ("2026-10-01", "2026-10-31", "100"),
    ("2026-10-01", "2026-11-30", "200"),
])
def test_complete_months(start, end, total):
    coverage = target_coverage(data(), DateRange(start=start, end=end))
    assert coverage.total == Decimal(total)
    assert coverage.reason is None


@pytest.mark.parametrize("start,end", [("2026-10-02", "2026-10-31"), ("2026-10-01", "2026-10-30"), ("2026-11-01", "2026-11-17")])
def test_partial_months_have_no_comparison(start, end):
    coverage = target_coverage(data(), DateRange(start=start, end=end))
    assert coverage.total is None
    assert "complete calendar months" in coverage.reason


def test_missing_target_is_not_zero():
    coverage = target_coverage(data(("2026-10-01",)), DateRange(start="2026-10-01", end="2026-11-30"))
    assert coverage.total is None
    assert "2026-11" in coverage.reason


@pytest.mark.parametrize("months,end", [(("2026-12-01", "2027-01-01"), "2027-01-31"), (("2024-02-01",), "2024-02-29"), (("9999-12-01",), "9999-12-31")])
def test_year_boundary_and_leap_year(months, end):
    assert target_coverage(data(months), DateRange(start=months[0], end=end)).total == 100 * len(months)


def test_order_filter_includes_edges_and_excludes_outside():
    dates = ["2026-09-30", "2026-10-01", "2026-10-31", "2026-11-01"]
    orders = [SalesOrder(order_id=str(i), order_date=d, customer="Demo", service="Support", revenue="1") for i, d in enumerate(dates)]
    selected = select_orders(BusinessData(orders=orders), DateRange(start="2026-10-01", end="2026-10-31"))
    assert [o.order_id for o in selected] == ["1", "2"]
    with pytest.raises(DataValidationError, match="No sales orders"):
        select_orders(BusinessData(orders=orders), DateRange(start="2025-01-01", end="2025-01-31"))

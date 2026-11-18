"""Date selection and target eligibility, independent of input file formats."""
import calendar
from datetime import date
from decimal import Decimal
from typing import Optional, Tuple

from core.exceptions import DataValidationError
from core.schemas import BusinessData, DateRange, Record, SalesOrder


class TargetCoverage(Record):
    total: Optional[Decimal] = None
    reason: Optional[str] = None


def select_orders(data: BusinessData, period: DateRange) -> Tuple[SalesOrder, ...]:
    orders = tuple(order for order in data.orders if period.contains(order.order_date))
    if not orders:
        raise DataValidationError("No sales orders were found in the selected date range.")
    return orders


def target_coverage(data: BusinessData, period: DateRange) -> TargetCoverage:
    """Never prorate monthly targets or substitute zero for absent months."""
    last_day = calendar.monthrange(period.end.year, period.end.month)[1]
    if period.start.day != 1 or period.end.day != last_day:
        return TargetCoverage(reason="Sales targets require complete calendar months.")
    targets = {target.month: target.sales_target for target in data.monthly_targets}
    month = period.start
    last_month = period.end.replace(day=1)
    total = Decimal("0.00")
    while True:
        if month not in targets:
            return TargetCoverage(reason="Missing sales target for {}.".format(month.strftime("%Y-%m")))
        total += targets[month]
        if month == last_month:
            break
        month = date(month.year + 1, 1, 1) if month.month == 12 else date(month.year, month.month + 1, 1)
    return TargetCoverage(total=total)

"""Deterministic sales calculations using normalized records only."""
from collections import defaultdict
from decimal import Decimal

from core.data_rules import select_orders, target_coverage
from core.schemas import DateRange, SourceData
from reports.base import ChartSpec, Metric, ReportData, ReportTable, money, round_decimal, snapshot_notes


class SalesSummaryBuilder:
    def build(self, data: SourceData, period: DateRange) -> ReportData:
        orders = sorted(select_orders(data, period), key=lambda order: (order.order_date, order.order_id))
        total = sum((order.revenue for order in orders), Decimal("0.00"))
        average = round_decimal(total / len(orders), "0.01")
        coverage = target_coverage(data, period)
        achievement = total / coverage.total * 100 if coverage.total is not None else None
        metrics = (
            Metric(key="total_revenue", label="Recorded revenue", value=total, unit="AUD"),
            Metric(key="total_orders", label="Total orders", value=len(orders), unit="count"),
            Metric(key="average_order_value", label="Average order value", value=average, unit="AUD"),
            Metric(key="sales_target", label="Sales target", value=coverage.total, unit="AUD", unavailable_reason=coverage.reason),
            Metric(key="target_achievement", label="Target achievement", value=achievement, unit="percent", unavailable_reason=coverage.reason),
        )
        summary = "Recorded revenue was {} from {} orders, with an average order value of {}.".format(money(total), len(orders), money(average))
        if achievement is None:
            summary += " Target comparison is unavailable: {}".format(coverage.reason)
        else:
            status = "met or exceeded the target" if total >= coverage.total else "was below the target"
            summary += " Recorded revenue reached {}% of the full-month target and {}.".format(round_decimal(achievement, "0.1"), status)
        notes = [
            "Currency: AUD; revenue excludes tax. Zero-value orders count toward order totals.",
            "Observed selected order dates: {} to {}. Results describe supplied records only; this does not establish complete coverage of the requested period.".format(orders[0].order_date, orders[-1].order_date),
            "Monthly targets are compared only for complete calendar-month selections with every target present. Targets are never prorated.",
        ]
        if coverage.reason:
            notes.append(coverage.reason)
        tables = [ReportTable(
            title="Sales details", columns=("Order ID", "Date", "Customer", "Service", "Revenue (AUD)"),
            rows=tuple((o.order_id, o.order_date.isoformat(), o.customer, o.service, "{:.2f}".format(o.revenue)) for o in orders),
        )]
        if data.snapshot is not None:
            tasks = data.snapshot.tasks
            completed = sum(task.completed for task in tasks)
            rate = Decimal(completed) / len(tasks) * 100
            tables.append(ReportTable(
                title="Separate demonstration task snapshot", columns=("Metric", "Value"),
                rows=(("Total tasks", str(len(tasks))), ("Completed", str(completed)),
                      ("Pending", str(len(tasks) - completed)), ("Completion rate", "{}%".format(round_decimal(rate, "0.1")))),
            ))
            notes.extend(snapshot_notes(data.snapshot))
        daily = defaultdict(lambda: Decimal("0.00"))
        for order in orders:
            daily[order.order_date] += order.revenue
        days = sorted(daily)
        return ReportData(
            report_type="sales_summary", title="Sales Summary", requested_period=period,
            period_label="Sales date range: {} to {} (inclusive)".format(period.start, period.end),
            metrics=metrics, summary=summary, notes=notes, tables=tables,
            chart=ChartSpec(kind="sales_trend", title="Recorded sales by order date", labels=tuple(day.isoformat() for day in days),
                            values=tuple(daily[day] for day in days), y_label="Revenue (AUD)",
                            caption="Points show totals on recorded order dates only. Gaps are not filled with zero or treated as complete daily coverage."),
        )

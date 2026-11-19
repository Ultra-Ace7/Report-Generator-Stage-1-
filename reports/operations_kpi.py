"""Snapshot KPIs; never infer historical monthly activity from undated tasks."""
from decimal import Decimal

from core.exceptions import DataValidationError
from core.schemas import DateRange, SourceData
from reports.base import ChartSpec, Metric, ReportData, ReportTable, round_decimal, snapshot_notes


class OperationsKpiBuilder:
    def build(self, data: SourceData, period: DateRange) -> ReportData:
        if data.snapshot is None:
            raise DataValidationError("Operations / KPI Report requires a task snapshot. Select the API or explicit offline fixture.")
        snapshot = data.snapshot
        total = len(snapshot.tasks)
        completed = sum(task.completed for task in snapshot.tasks)
        pending = total - completed
        rate = Decimal(completed) / total * 100
        benchmark = data.benchmark.completion_rate_target * 100 if data.benchmark else None
        gap = rate - benchmark if benchmark is not None else None
        reason = None if benchmark is not None else "No demonstration snapshot benchmark was selected."
        metrics = (
            Metric(key="total_tasks", label="Total tasks", value=total, unit="count"),
            Metric(key="completed_tasks", label="Completed tasks", value=completed, unit="count"),
            Metric(key="pending_tasks", label="Pending tasks", value=pending, unit="count"),
            Metric(key="completion_rate", label="Task completion rate", value=rate, unit="percent"),
        )
        summary = "The demonstration snapshot contains {} tasks: {} completed and {} pending. Completion rate is {}%.".format(total, completed, pending, round_decimal(rate, "0.1"))
        if benchmark is None:
            summary += " Benchmark comparison is unavailable because no snapshot benchmark was selected."
        elif gap == 0:
            summary += " The completion rate meets the demonstration benchmark."
        else:
            direction = "above" if gap > 0 else "below"
            summary += " This is {} percentage points {} the demonstration benchmark.".format(round_decimal(abs(gap), "0.1"), direction)
        summary += " This is not a measure of monthly company performance."
        notes = list(snapshot_notes(snapshot))
        notes.append("Created records task creation, not completion. Snapshot KPIs include all supplied tasks; the date range does not filter them.")
        notes.append("The requested date range is context only for this report. No historical task filtering is possible with this source.")
        if reason:
            notes.append(reason)
        return ReportData(
            report_type="operations_kpi", title="Operations / KPI Report", requested_period=period,
            period_label="Task snapshot as of {} | Requested range {} to {} (context only)".format(snapshot.captured_at.isoformat(), period.start, period.end),
            metrics=metrics, summary=summary, notes=notes,
            tables=(ReportTable(title="Snapshot KPI comparison", columns=("Metric", "Value"), rows=tuple((m.label, m.display) for m in metrics)),
                    ReportTable(title="Task snapshot details", columns=("Task ID", "Task Name", "User ID", "Status", "Created"),
                                rows=tuple((str(t.task_id), t.title, str(t.user_id), "Completed" if t.completed else "Pending", t.created.isoformat() if t.created else "Not provided") for t in sorted(snapshot.tasks, key=lambda t: t.task_id)))),
            chart=ChartSpec(kind="task_status", title="Demonstration task snapshot", labels=("Completed", "Pending"),
                            values=(Decimal(completed), Decimal(pending)), y_label="Number of tasks",
                            caption="{} | {} | Undated demo tasks; not monthly activity.".format(snapshot.mode, snapshot.captured_at.isoformat())),
        )

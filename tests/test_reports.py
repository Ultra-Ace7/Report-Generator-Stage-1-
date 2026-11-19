from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from PIL import Image
import pytest

from core.exceptions import DataValidationError
from core.schemas import DateRange, MonthlyTarget, SalesOrder, SnapshotBenchmark, SourceData, Task, TaskSnapshot
from reports.operations_kpi import OperationsKpiBuilder
from reports.sales_summary import SalesSummaryBuilder
from renderer.chart_builder import render_chart
from sources.api_reader import OfflineTaskReader
from sources.base import merge_sources
from sources.csv_excel import CsvExcelReader
from sources.pdf_reader import PdfMetricsReader

PERIOD = DateRange(start="2026-10-01", end="2026-10-31")
SAMPLES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def order(identifier="1", revenue="10.00", day="2026-10-01"):
    return SalesOrder(order_id=identifier, order_date=day, customer="Demo", service="IT", revenue=revenue)


def snapshot(completed=(True, False)):
    return TaskSnapshot(tasks=[Task(task_id=i + 1, user_id=1, title="Demo", completed=value) for i, value in enumerate(completed)],
                        captured_at="2026-11-17T09:00:00+11:00", source="Synthetic fixture", mode="offline_fixture")


def metrics(report):
    return {metric.key: metric for metric in report.metrics}


@pytest.fixture
def sample_data():
    return merge_sources(CsvExcelReader(SAMPLES / "sales.csv").read(), PdfMetricsReader(SAMPLES / "monthly_metrics.pdf").read(),
                         OfflineTaskReader(SAMPLES / "todos_fixture.json", SAMPLES / "todos_fixture_metadata.json").read())


def test_october_sales_known_values_and_all_three_sources(sample_data):
    report = SalesSummaryBuilder().build(sample_data, PERIOD)
    values = metrics(report)
    assert values["total_revenue"].value == Decimal("7000.00")
    assert values["total_orders"].value == 4
    assert values["average_order_value"].value == Decimal("1750.00")
    assert values["sales_target"].value == Decimal("8000.00")
    assert values["target_achievement"].value == Decimal("87.5")
    assert len(report.tables[0].rows) == 4
    assert report.tables[1].rows[0] == ("Total tasks", "5")
    assert "below the target" in report.summary
    assert "offline_fixture" in " ".join(report.notes)
    assert sum(report.chart.values) == Decimal("7000.00")
    assert "supplied records only" in " ".join(report.notes)


def test_partial_month_has_no_target_comparison(sample_data):
    report = SalesSummaryBuilder().build(sample_data, DateRange(start="2026-11-01", end="2026-11-17"))
    values = metrics(report)
    assert values["total_revenue"].value == 8000
    assert values["average_order_value"].value == 2000
    assert values["target_achievement"].value is None
    assert values["sales_target"].unavailable_reason
    assert "unavailable" in report.summary


def test_missing_target_and_snapshot_are_optional():
    report = SalesSummaryBuilder().build(SourceData(orders=[order()]), PERIOD)
    assert metrics(report)["sales_target"].value is None
    assert len(report.tables) == 1
    assert "Missing sales target" in report.summary


def test_no_selected_orders_is_an_error():
    with pytest.raises(DataValidationError, match="No sales orders"):
        SalesSummaryBuilder().build(SourceData(orders=[order(day="2026-09-30")]), PERIOD)


def test_money_half_up_rounding_daily_aggregation_and_order_sorting():
    data = SourceData(orders=[order("b", "0.01"), order("a", "0.00")])
    report = SalesSummaryBuilder().build(data, PERIOD)
    assert metrics(report)["average_order_value"].value == Decimal("0.01")
    assert report.chart.values == (Decimal("0.01"),)
    assert [row[0] for row in report.tables[0].rows] == ["a", "b"]


@pytest.mark.parametrize("amount,status", [("100", "met or exceeded"), ("120", "met or exceeded"), ("0", "below")])
def test_sales_target_status(amount, status):
    report = SalesSummaryBuilder().build(SourceData(orders=[order(revenue=amount)], monthly_targets=[MonthlyTarget(month="2026-10-01", sales_target="100")]), PERIOD)
    assert status in report.summary
    assert metrics(report)["total_orders"].value == 1


def test_multi_month_target_sum(sample_data):
    result = SalesSummaryBuilder().build(sample_data, DateRange(start="2026-10-01", end="2026-11-30"))
    assert metrics(result)["sales_target"].value == 18000
    assert metrics(result)["total_revenue"].value == 15000
    assert len(result.tables[0].rows) == 8


def test_operations_known_values(sample_data):
    report = OperationsKpiBuilder().build(sample_data, PERIOD)
    values = metrics(report)
    assert [values[key].value for key in ("total_tasks", "completed_tasks", "pending_tasks", "completion_rate")] == [5, 3, 2, 60]
    assert "20.0 percentage points below" in report.summary
    assert "not a measure of monthly company performance" in report.summary
    assert "context only" in report.period_label
    assert len(report.tables[1].rows) == 5
    assert report.chart.values == (Decimal(3), Decimal(2))


def test_operations_date_range_does_not_filter_tasks(sample_data):
    builder = OperationsKpiBuilder()
    first = builder.build(sample_data, PERIOD)
    other = builder.build(sample_data, DateRange(start="2020-01-01", end="2020-01-02"))
    assert first.metrics == other.metrics
    assert first.chart == other.chart
    assert "2020-01-01" in other.period_label


def test_operations_requires_snapshot():
    with pytest.raises(DataValidationError, match="requires a task snapshot"):
        OperationsKpiBuilder().build(SourceData(), PERIOD)


def test_missing_benchmark_is_not_zero():
    report = OperationsKpiBuilder().build(SourceData(snapshot=snapshot()), PERIOD)
    assert "completion_benchmark" not in metrics(report)
    assert "benchmark_gap" not in metrics(report)
    assert "unavailable" in report.summary


@pytest.mark.parametrize("states,target,rate,gap,status", [
    ((True, True), "0.8", 100, 20, "above"),
    ((False, False), "0.8", 0, -80, "below"),
    ((True, False), "0.5", 50, 0, "meets"),
    ((False,), "0", 0, 0, "meets"),
])
def test_operations_benchmark_boundaries(states, target, rate, gap, status):
    report = OperationsKpiBuilder().build(SourceData(snapshot=snapshot(states), benchmark=SnapshotBenchmark(completion_rate_target=target)), PERIOD)
    assert metrics(report)["completion_rate"].value == rate
    assert "benchmark_gap" not in metrics(report)
    assert status in report.summary


def test_builders_are_deterministic_and_preserve_input(sample_data):
    original = sample_data.model_dump_json()
    for builder in (SalesSummaryBuilder(), OperationsKpiBuilder()):
        assert builder.build(sample_data, PERIOD) == builder.build(sample_data, PERIOD)
    assert sample_data.model_dump_json() == original


@pytest.mark.parametrize("builder", [SalesSummaryBuilder, OperationsKpiBuilder])
def test_chart_is_valid_png(sample_data, builder):
    png = render_chart(builder().build(sample_data, PERIOD).chart)
    with Image.open(BytesIO(png)) as image:
        assert image.format == "PNG"
        assert image.width >= 1000
        assert image.height >= 600
        image.verify()


def test_zero_and_single_day_charts_render():
    reports = [SalesSummaryBuilder().build(SourceData(orders=[order(revenue="0")]), PERIOD),
               OperationsKpiBuilder().build(SourceData(snapshot=snapshot((False,))), PERIOD)]
    for report in reports:
        with Image.open(BytesIO(render_chart(report.chart))) as image:
            image.verify()

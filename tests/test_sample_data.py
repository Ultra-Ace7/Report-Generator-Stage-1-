"""Fixture consistency checks; production readers are implemented in Step 3."""
import csv
import json
from decimal import Decimal
from pathlib import Path

import pdfplumber

from core.data_rules import select_orders, target_coverage
from core.schemas import BusinessData, DateRange, SnapshotBenchmark, TaskSnapshot

SAMPLES = Path(__file__).resolve().parents[1] / "sample_data"


def test_sales_fixture_totals_and_target_coverage():
    with (SAMPLES / "sales.csv").open(newline="", encoding="utf-8") as source:
        orders = list(csv.DictReader(source))
    reference = json.loads((SAMPLES / "metrics_reference.json").read_text())
    data = BusinessData(orders=orders, monthly_targets=reference["monthly_targets"])
    october = DateRange(start="2026-10-01", end="2026-10-31")
    selected = select_orders(data, october)
    assert len(selected) == 4
    assert sum(o.revenue for o in selected) == Decimal("7000.00")
    assert target_coverage(data, october).total == Decimal("8000.00")
    november = DateRange(start="2026-11-01", end="2026-11-17")
    assert sum(o.revenue for o in select_orders(data, november)) == Decimal("8000.00")
    assert target_coverage(data, november).total is None


def test_api_fixture_is_explicitly_offline_and_has_expected_counts():
    raw = json.loads((SAMPLES / "todos_fixture.json").read_text())
    metadata = json.loads((SAMPLES / "todos_fixture_metadata.json").read_text())
    tasks = [dict(task_id=r["id"], user_id=r["userId"], title=r["title"], completed=r["completed"]) for r in raw]
    snapshot = TaskSnapshot(tasks=tasks, **metadata)
    assert snapshot.mode == "offline_fixture"
    assert len(snapshot.tasks) == 5
    assert sum(task.completed for task in snapshot.tasks) == 3
    assert not any("date" in key.lower() for row in raw for key in row)


def test_pdf_fixture_matches_reference_values():
    reference = json.loads((SAMPLES / "metrics_reference.json").read_text())
    benchmark = SnapshotBenchmark(**reference["snapshot_benchmark"])
    with pdfplumber.open(SAMPLES / "monthly_metrics.pdf") as pdf:
        assert len(pdf.pages) == 1
        text = pdf.pages[0].extract_text()
    for target in reference["monthly_targets"]:
        assert target["month"][:7] in text
        assert target["sales_target"] in text
    assert "Completion Rate Target: {:.0f}%".format(benchmark.completion_rate_target * 100) in text
    assert benchmark.scope in text

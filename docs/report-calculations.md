# Report calculations and charts (Step 4)

## Preview

```bash
python -m scripts.preview_reports
python -m scripts.preview_reports --start 2026-11-01 --end 2026-11-17
```

The command uses the supplied sales CSV, metrics PDF and explicitly offline task
fixture. It prints calculated results and writes two JSON content previews and
two PNG charts to `output/preview/`. Re-running the same date range replaces its
preview files. No Word template or DOCX output is implemented in this step.

## Shared contracts

`core.schemas.SourceData` owns the normalized inputs. It is also re-exported
from `sources.base` to preserve existing reader imports. Report builders import
only core models and shared report contracts, not CSV, PDF or API readers.

Both builders implement `build(data, period) -> ReportData`. The result contains
metrics, deterministic prose, explicit notes, variable-length tables and a
ChartSpec. A future Word renderer can consume this contract for either report.
Chart rendering is separate from calculations and uses a non-GUI Matplotlib
canvas that returns PNG bytes; the builder does not write files or access APIs.

## Sales Summary

- Revenue: exact Decimal sum of orders in the inclusive selected date range.
- Orders: number of selected records, including zero-value orders.
- Average order value: revenue / count, rounded to cents using ROUND_HALF_UP.
- Sales target: sum of targets only for complete calendar-month selections with
  every month's target present. Otherwise target and achievement are unavailable.
- Achievement: recorded revenue / target * 100. Comparison uses unrounded values.
- Details: date then order-ID order; no rows are truncated.
- Trend: daily sums for recorded order dates, sorted chronologically. Dates with
  no records are not imputed as zero. The chart uses actual calendar spacing.
- Optional API tasks: separate snapshot table, with mode, timestamp and source.
  This lets one report include all three input types without falsely joining
  sales customers to demonstration API tasks.

No records in the selected range is an error. The report always states observed
record dates and warns that supplied records do not prove complete coverage.
A full-month selection does not turn November's partial sample into complete
actuals. Results are described as recorded revenue rather than a forecast.

## Operations / KPI Report

A nonempty task snapshot is required; sales inputs are optional and are not used
in task calculations. The selected date range is shown as context only.

- Total: snapshot task count.
- Completed: count whose normalized boolean is true.
- Pending: total minus completed.
- Completion rate: completed / total * 100.
- Demo benchmark: optional PDF snapshot benchmark * 100.
- Gap: completion rate minus benchmark, in percentage points (not percent change).
- Task status chart: completed/pending counts, including zero-valued categories.
- KPI comparison table and task details retain all rows.

Missing benchmarks are unavailable, never silently zero. A genuine zero
benchmark is valid. Prose classifies below/meeting/above the demo benchmark using
unrounded values. No monthly-company-performance claim is made from these tasks.

## Formatting and verification

Money is displayed in AUD with two decimals. Rates and percentage-point gaps are
displayed with one decimal using ROUND_HALF_UP; numeric results remain Decimal.
Builders are deterministic and do not alter their input. Offline fixtures make
the expected October controls reproducible: revenue 7000.00, 4 orders, average
1750.00, target 8000.00, achievement 87.5%; tasks 5, completed 3, pending 2,
completion 60%, benchmark 80%, gap -20 percentage points.

## Verified results

On 18 November 2026 (Australia/Melbourne), the full Python 3.9 suite passed:
137 tests, including 23 new report/chart/preview checks. There were 14
third-party Matplotlib/Pyparsing deprecation warnings and no test failures.
Both October and 1-17 November previews ran successfully. The latter correctly
omits monthly target achievement. PNG previews were visually inspected.

# Data contract (Step 2)

All supplied data is synthetic. These are input fixtures, not generated business
reports. The supplied table fixture is CSV; the reader also supports values-only .xlsx
files with a Sales worksheet and the same columns.

## Sales records: sample_data/sales.csv

Each row is one order, not an invoice line or payment. Required columns:

| Field | Type | Rule |
| --- | --- | --- |
| order_id | text | Nonblank, case-sensitive, unique across all selected files |
| order_date | date | ISO YYYY-MM-DD; no timestamps or numeric epochs |
| customer | text | Nonblank synthetic company name |
| service | text | Nonblank service description |
| revenue | decimal | 0 to 999999999999.99 AUD, at most two decimal places |
| currency | text | AUD only; normalized model defaults to AUD |

Revenue represents recognized sales excluding tax. Refunds/negative sales are
not supported in this initial dataset. Zero-value orders are allowed and count
as orders. Currency symbols, thousands separators, NaN and infinity are rejected.
Money uses Decimal; inputs are not silently rounded. Whitespace around text is
trimmed, and unexpected model fields are rejected.

Readers must explicitly map source fields and Excel dates into these normalized
models. They must combine selected files before enforcing unique order IDs.
Selecting the same data twice must fail rather than double-count it.

## Monthly targets: sample_data/monthly_metrics.pdf

A one-page text-based PDF with a two-column sales target table:
`Reporting Month` (YYYY-MM) and `Sales Target (AUD)` (positive decimal).
The reader will normalize the month to its first day (YYYY-MM-01).
Exactly one sales target per month is allowed. Scanned PDFs and arbitrary layouts
are not supported by the initial PDF reader.

A separate section contains `Completion Rate Target: 80%` with the explicit scope
`demo_task_snapshot`. This is a demonstration snapshot benchmark, not a monthly
operational target. Normalize percentages to a Decimal fraction between 0 and 1.
`metrics_reference.json` records fixture expectations for tests; it must not be
used as a substitute for reading the PDF in production.

## API task snapshot

`todos_fixture.json` contains five locally authored records in the shape of
JSONPlaceholder `/todos`: `userId`, `id`, `title`, `completed`. IDs are positive
integers and `completed` must be a JSON boolean, never a string or number.
The reader maps IDs to `user_id` and `task_id`. Duplicate task IDs are rejected.

`todos_fixture_metadata.json` explicitly marks the sample as `offline_fixture`.
Its timestamp is a synthetic fixture timestamp, not evidence of a live API fetch.
A live call must set its actual timezone-aware retrieval timestamp and label its
mode `live_demo`. Empty snapshots are rejected; an empty API response is not
reported as a 0% completion rate.

Task data has no historical dates. The report date range filters sales only;
task results must appear in a separate snapshot section with source, mode and
timestamp. These public-demo-shaped tasks are not linked to sales customers.
The snapshot benchmark may be compared to that demo snapshot, never to monthly
company performance. API connectivity and failure handling are covered by the Step 3 adapters.

## Date selection and target comparison

- Start and end are inclusive; reversed ranges are invalid.
- No orders in the selected range raises a user-facing DataValidationError.
- Monthly sales comparison is available only when the range starts on the first
  day and ends on the last day of a month and every covered month has a target.
- Partial months or missing targets return `total=None` with a reason, not zero.
- Multi-month comparison uses the sum of all covered monthly targets.
- Coverage does not prove completeness of actuals. Always disclose source coverage.
  November sample sales stop at 17 November; they are neither a forecast nor a
  complete month's actuals, even if a user selects the entire month.

## Independent expected values

| Selection | Orders | Revenue AUD | Average order AUD | Target AUD |
| --- | ---: | ---: | ---: | ---: |
| October 2026 | 4 | 7000.00 | 1750.00 | 8000.00 |
| 1-17 November 2026 | 4 | 8000.00 | 2000.00 | Unavailable: partial month |

October target achievement will be 87.5%. The offline task snapshot has 5 tasks,
3 completed, 2 pending and a 60% completion rate versus the 80% demo benchmark
(a difference of -20 percentage points). These are expected controls for future
report builders; this step does not implement report summaries or charts.

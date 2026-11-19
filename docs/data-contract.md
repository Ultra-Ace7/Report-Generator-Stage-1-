# Data contract (Step 2)

All supplied data is synthetic. These are input fixtures, not generated business
reports. The supplied table fixture is CSV; the reader also supports values-only .xlsx
files with the same columns. The UI defaults to the first worksheet; an optional
name selects another worksheet. The CLI defaults to `Sales` for compatibility.

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

## External CSV/XLSX column names

The internal six-field schema stays strict. Input headers are trimmed,
case-insensitive, and runs of spaces, underscores or hyphens are equivalent.
Mapping is by explicit name, never position or fuzzy inference.

| Canonical field | Accepted aliases (in addition to the canonical name) |
| --- | --- |
| order_id | Order ID, Order Number, Transaction ID |
| order_date | Date, Order Date, Transaction Date |
| customer | Customer, Customer Name, Client, Client Name |
| service | Service, Service Type, Product |
| revenue | Revenue, Sales Amount, Amount, Total Amount |
| currency | Currency, Currency Code |

Each required field must map exactly once. Unrelated additional columns are
ignored before model validation; rows must still match the full header width.
Missing currency is an error even though the internal model has an AUD default.
For example, missing fields produce `Missing required sales fields: revenue,
currency.` followed by accepted aliases. Duplicate synonyms produce
`Multiple columns map to 'revenue': Revenue, Total Amount. Please keep only one.`
Invalid values identify the physical row, canonical field and validation reason.

All revenue aliases retain the same meaning: recognized sales excluding tax.
`Amount` and `Total Amount` are rejected when other headers contain a separate
word tax, taxes, GST, VAT, refund(s) or discount(s), including space/underscore/
hyphen-separated names. No tax/refund/discount arithmetic is inferred. Supply a
verified Revenue field instead. This explicit guard is not a general financial
schema interpreter; users must verify the financial meaning of all inputs.
Unknown aliases are not guessed. Excel formula/error cells remain rejected,
including in extra columns. PDF and API contracts are unchanged.

Blank UI worksheet selection reads each workbook's own first worksheet. An
explicit name applies to every uploaded workbook and must exist in each; there
is no fallback to a different sheet. Use a common sheet name or leave the setting
blank when combining workbooks with differently named first worksheets.

## Sales-order PDF tables

The UI PDF input and CLI `--metrics` path now dispatch either the existing target
layout or text-based sales tables with visible cell borders. Sales tables must
contain the six canonical fields or documented aliases. Wrapped headers are
normalized as whitespace. Repeated headers on subsequent pages are skipped;
every data row is validated. Multi-page tables must repeat their header on each
page; unlabelled continuation tables are unsupported. Scanned/image-only PDFs,
merged cells and arbitrary unruled layouts are not supported. Do not use these
layouts for input: table extraction is not general document understanding.

PDF sales dates accept ISO YYYY-MM-DD and explicit year-first YYYY/M/D, e.g.
2026/10/3 becomes 2026-10-03. Ambiguous day/month dates are rejected. Amounts and
AUD currency follow the same strict sales model; no values are invented.
A PDF containing only targets still requires actual sales from another source.
The current UI accepts one PDF per run; a sales PDF can be combined with CSV,
Excel or an API. Duplicate orders across sources are rejected.

`sample_data/sales_orders.pdf` contains five fictional October orders, total
AUD 7,390.00 and average AUD 1,478.00. Select 1-31 October 2026 to reproduce these
values. It has no sales target; target comparison is unavailable.

# Input readers (Step 3)

## Run a source check

From the project root, with the existing virtual environment activated:

```bash
python -m scripts.check_sources
python -m scripts.check_sources --live-api
python -m pytest -q
```

The default check is explicitly offline: 8 orders, 2 monthly targets and a
5-task fixture with 3 completed tasks. `--live-api` calls the real public endpoint;
counts and retrieval timestamp can differ. It never falls back to fixture data.
The check writes logs to `logs/report_generator.log`, excluded from Git. Errors
print a short explanation and return exit code 1. Neither command creates a report.
Automated tests are offline and use HTTPX MockTransport for API responses/failures.

## Reader contract

Every reader implements `read() -> SourceData`. SourceData contains validated
orders, monthly targets and optional snapshot/benchmark values. Readers depend
on normalized models, not on Sales Summary or Operations report builders.
`merge_sources()` combines the results and rejects duplicate order/month keys,
multiple task snapshots or multiple snapshot benchmarks.

To add an adapter, implement this method, normalize into the existing models (or
extend models for new business facts), use `read_boundary()` for consistent
errors/logging, and add focused success/failure tests. Future UI/CLI orchestration
will choose adapters without rewriting the report calculations.

## CSV and Excel

`CsvExcelReader(path, sheet_name="Sales")` supports UTF-8 CSV (including BOM) and
`.xlsx` files. All six documented columns are required; order may vary. Header
names are trimmed but case-sensitive. Missing, duplicate and extra columns fail.
Blank rows are skipped; nonblank malformed rows fail with a row number when
possible. Empty data is an error. IDs remain strings, so leading zeros survive.
CSV uses the standard-library reader to avoid automatic date/number conversion.

Excel uses openpyxl to retain cell types. The named `Sales` worksheet must exist;
pass another sheet name explicitly if necessary. Real Excel dates at midnight
are normalized to calendar dates, while timestamps with a time component fail.
Formula/error cells fail rather than relying on potentially stale cached values.
Use values-only tables and text cells for IDs. Legacy `.xls` is unsupported.

## PDF

`PdfMetricsReader(path)` uses pdfplumber to extract text from the actual PDF.
It supports the layout demonstrated by `sample_data/monthly_metrics.pdf`, with
one sales-target table and one scoped task benchmark. It validates every table
row; malformed target rows must not disappear silently. Empty/scanned, damaged,
encrypted, duplicate-month and unsupported-layout inputs produce clear errors.
No OCR or arbitrary PDF-layout inference is implemented. The JSON reference file
is never read by this adapter.

## API and explicit offline mode

`ApiTaskReader(client=None, timeout=10.0)` reads the JSONPlaceholder `/todos`
endpoint. The timeout is a per-operation HTTPX timeout, not a total wall-clock
budget. Redirects are not followed. HTTP failures, connection failures, timeouts,
invalid JSON, empty responses, invalid records and duplicate task IDs fail.
A supplied HTTPX client remains owned by its caller; internally created clients
are closed. There are no automatic retries or silent fixture fallbacks.

`OfflineTaskReader(path, metadata_path)` uses locally authored JSON and requires
metadata mode `offline_fixture`, a source label and a timezone-aware timestamp.
Live data gets the actual retrieval timestamp and mode `live_demo`. Neither mode
represents historical monthly task activity.

## Error and log boundaries

Expected IO/API errors raise `SourceReadError`; invalid business data raises
`DataValidationError`. Both derive from `ReportError`, which the eventual UI/CLI
will catch. Libraries emit logs through `report_generator.sources`; entry points
configure log destinations. Error logs omit raw records and response bodies.
The verification command already handles these errors without a traceback.

## References

- HTTPX transports/testing: https://www.python-httpx.org/advanced/transports/
- Public demonstration API: https://jsonplaceholder.typicode.com/

## Verification on 18 November 2026 (Australia/Melbourne)

- Full suite: 114 passed; 13 existing third-party Matplotlib/Pyparsing deprecation warnings.
- Offline source check: 8 sales orders, 2 targets, 5 tasks / 3 completed.
- Live source check: public API returned 200 tasks / 90 completed; all three
  source types were read and merged successfully. These are observed demo counts,
  not guaranteed future API values or company performance metrics.
- Dependency consistency check and Git whitespace check passed.
- Report calculations, Word rendering and report UI/CLI wiring remain future steps.

# Testing and resilience checks

Run the complete suite from the project directory:

```bash
python -m pytest -q
```

The 19 November 2026 run passed 186 cases, including 9 new resilience cases.
There were 14 third-party deprecation warnings. This count is not a line or
branch coverage percentage. Earlier verification records retain their historical
177-case results.

`tests/test_resilience.py` covers:

- Unicode and long text through CSV to DOCX, including paths with spaces and
  Chinese characters, and exact cent arithmetic.
- 10,000 input rows with independent count and total checks.
- Five alternating report generations without accumulating rows or changing
  the source template.
- Exactly 20 MiB and one byte over the upload admission limit.
- Two independent AppTest sessions, including failure in one without changing
  the other's result. This is not a simultaneous browser load test.
- Three repeated UI generations without duplicate results or controls.
- Success, simulated API failure and explicit offline recovery in one session,
  ensuring an old download is not presented as a successful new result.

## Optional performance observation

```bash
python -m scripts.benchmark_report --rows 1000
```

The benchmark uses temporary synthetic CSV data, generates a real DOCX, checks
its row count and revenue, and prints JSON measurements. It does not modify
sample data or the template. A 1,000-row run on macOS / Python 3.9.6 took 4.377
seconds for generation, with 136.77 MiB process peak RSS. Input was 51,945 bytes;
DOCX was 102,583 bytes. These are single-run observations, not performance limits.
RSS includes imports and verification and is available on macOS/Linux; other
platforms report null. The benchmark is intentionally separate from normal tests
so machine speed does not create a brittle test assertion.

## Limits and further manual verification

- Text round-trip assertions do not verify visible glyphs or page layout. Check
  long and multilingual reports in the Word-compatible viewers being supported.
- AppTest session isolation does not prove concurrent-request scalability.
- One process peak-memory result does not prove absence of memory leaks.
- Windows has not been exercised in a real Windows environment.
- Existing API tests use controlled responses; previous live samples provide
  separate evidence of real connectivity, not current service availability.

## Data Inputs refactor verification — 19 November 2026

- Python 3.9.6: `python -m pytest -q` completed with **237 passed**, 14 existing
  Matplotlib/Pyparsing deprecation warnings (9.48 seconds in this local run).
- `python -m pip check`: no broken requirements. `git diff --check`: clean.
- A fresh Streamlit process returned HTTP 200 / `ok` from its health endpoint;
  the temporary verification process was then stopped. The existing application
  was also opened in a browser and generated a sample report with both Word and
  PDF download buttons enabled.
- `python -m scripts.check_sources --live-api` succeeded using the protected
  transport: 8 sales orders, 2 PDF targets, 200 API tasks / 90 completed.
  Observed snapshot timestamp: `2026-11-19T05:58:37.228082+00:00`.
  This command validates sources; it does not create a report.
- The new UI end-to-end test uploads CSV and PDF together and uses a controlled
  HTTP response through the API adapter. It reopens the final DOCX and asserts
  revenue AUD 7,000.00, PDF target AUD 8,000.00, three tasks and 33.3% completion.
  The same test verifies that the original template hash is unchanged.
- Other new checks cover offline CSV with network access forbidden, first/named/
  missing Excel worksheets, PDF-only file input with task data, API-only
  Operations/KPI, missing sales, malformed/disguised files, multiple-file merging,
  duplicate orders, ambiguous PDFs, invalid/private URLs, mixed DNS answers,
  IP pinning with original TLS hostname, DNS errors and blocked redirects.
- Existing timeout, HTTP, invalid JSON/schema, recovery, CLI, both-report,
  rendering, PDF-export and session-isolation tests remain in the full suite.

The original Stage 1 architecture, report calculations, immutable template,
three-source capability and two report types remain intact. CLI arguments retain
their original defaults; only the UI defaults an empty Excel worksheet name to
the first worksheet. See [input workflow and limitations](running-the-app.md).
Automated API tests use controlled responses and are not a guarantee of external
service availability. This run does not repeat the historical clean installation
or every previous visual pagination check.

## Sales API verification — 19 November 2026

Full suite: 297 passed, 14 existing dependency deprecation warnings (10.31 s).
Sales API tests cover canonical/alias JSON, missing and invalid values, duplicate
IDs within/across sources, empty/wrong schemas, HTTP/timeout/JSON/size failures,
unsafe URLs, API-only CLI/UI, combined sources and final DOCX generation with a
chart and unchanged template. Existing task API, offline, CLI and network
protection regression tests remain in the suite. The documented offline HTTP
mock command was also run successfully to a new temporary DOCX output.

## Current sample-data migration — 19 November 2026

Full suite executed after the sample-folder and UI changes: **320 passed**,
14 existing Matplotlib/Pyparsing deprecation warnings, 11.21 seconds locally.
The 11 current sample files each generate a DOCX in integration tests, checking
sales totals or task completion rates, charts, detail rows and template immutability.
October sales: 5 orders / AUD 7,390.00; November: 5 / AUD 8,650.00.
October tasks: 12 / 9 completed (75%); November: 10 / 7 completed (70%).
The PDF filename Sales_2026_10-11.pdf contains October orders only.

Old fixed numerical fixtures were moved to tests/fixtures; they are independent
regression inputs, not restored demonstration data. UI tests now upload files
explicitly instead of using removed sample checkboxes. Source-check, report-preview
and sample-generation scripts now use the current demonstration paths. The README
quick-start CLI was run successfully with current October sales, exit code 0,
verified total/average values, 0.84 seconds with dependencies already installed.
That execution time does not measure a fresh dependency installation.

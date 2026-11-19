# TechInnovate Report Generator

Generate Sales Summary and Operations/KPI reports as branded Word documents with
summaries, tables and charts. Optional PDF download is available in the UI.
Both reports share a template using the official TechInnovate logo; this project
and its supplied data are an internship demonstration, not company-issued reports.

## Quick start: first report in under 10 minutes

Prerequisites: Python 3.9, this repository downloaded, and internet access to install
dependencies. Run from the project root on macOS/Linux:

```bash
python3.9 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, create the environment with `py -3.9 -m venv venv` and activate using
`venv\Scripts\activate` in Command Prompt. Skip environment creation if it already
exists. Windows has not been verified.

Open `output/first_sales_report.docx`. Expected results: five orders, revenue
**AUD 7,390.00** and average order value **AUD 1,478.00**. No target is supplied
by this command, so target comparison is unavailable. This report runs
offline after installation; no API key, database or Microsoft Word is required
for generation. Existing output files are never overwritten: use a new filename
on subsequent runs. Python installation and network speed affect setup time;
[historical clean-install verification](docs/requirements-verification.md)
records an uncached dependency installation plus first report in 48.35 seconds
with Python already installed.

## One-command generation without UI

After setup, the last command above is the complete generation command: no
browser, prompts or Streamlit server are needed. Other examples:

```bash
# Sales Summary from the bundled CSV (offline)
python cli.py --report sales_summary --start 2026-10-01 --end 2026-10-31 --sales sample_data/Sales_Summary_Dummy_Data/sales_2026-10.csv --output output/cli_sales_demo.docx

# KPI using the live public task API (internet required)
python cli.py --report operations_kpi --start 2026-10-01 --end 2026-10-31 --tasks live --task-api-url https://jsonplaceholder.typicode.com/todos --output output/cli_kpi_demo.docx
```

Both commands above can be copied after activating the environment and entering
the project root. Use a new output filename if the file already exists.
Sales API-only usage requires your own compatible endpoint; see [Sales API](docs/sales-api.md).
Use `--task-api-url` with `--tasks live` to supply another compatible public HTTPS
task endpoint; omitting it keeps the JSONPlaceholder default.
Use `python cli.py --help` for options. CLI exit codes: 0 success, 1 input or
report failure, 2 invalid command arguments. Logs: `logs/report_generator.log`.
Stage 2 can schedule the same command with the virtual environment's Python,
a project-root working directory and a unique output filename for each run.
Scheduling and email delivery themselves are outside Stage 1.

## Browser interface and input formats

```bash
python -m streamlit run app.py --server.address 127.0.0.1
```

Open http://127.0.0.1:8501. Choose a report and dates, upload files and/or enable
REST API fetching, then generate and download. Upload limit: **20 MB per file**.
For API-only runs, disable Upload Files. Word and PDF downloads appear side by
side; PDF export requires local LibreOffice. Word remains available if conversion
fails. See [PDF setup](docs/pdf-export.md).

| Report | Required data | Supported UI inputs |
| --- | --- | --- |
| Sales Summary | Actual orders and revenue | Sales CSV/XLSX, bordered text-table PDF, or Sales orders API; optional metrics PDF and task API overview |
| Operations/KPI | Task records | Task CSV/XLSX, bordered text-table PDF, or Task API; choose uploaded tasks or API per run |

- **Sales fields:** `order_id`, `order_date`, `customer`, `service`, `revenue`,
  `currency`. Documented aliases such as Order Number, Client Name and Sales Amount
  are supported; case and separators are normalized. Currency is AUD, money is
  nonnegative with at most two decimal places. Ambiguous mappings and duplicates
  fail. Sales dates filter inclusively; target comparison needs complete months.
- **Task fields:** `Task ID`, `Task Name`, `User ID`, `Status`, `Created`.
  IDs are positive integers, Status is Completed/Pending, Created is YYYY-MM-DD
  (year-first YYYY/M/D is also supported). Legacy task files and JSONPlaceholder
  `userId`, `id`, `title`, `completed` remain compatible; absent creation dates
  display Not provided. KPIs show task counts and completion rate for all supplied
  tasks. Created is not a completion date; selected dates do not filter tasks.
- **Excel:** optional worksheet name; blank in the UI uses each workbook's first
  sheet. CLI `--sheet` defaults to Sales. Formula/error cells are rejected.
- **PDF:** sales/task input requires extractable text and visible table borders;
  repeated headers are required for multi-page tables. The documented metrics
  layout supplies targets only. No OCR or arbitrary document inference.
- **Multiple files:** sales and task IDs must be unique across selected inputs.
  Sales UI accepts at most one PDF; KPI accepts multiple task files. CLI supports
  sales CSV/XLSX via `--sales`, either sales/metrics PDF via `--metrics`, and task
  API via `--tasks live`; task-file upload is currently UI-only.
- **API:** select Sales orders or Task data explicitly. Sales JSON is an array
  of complete sales records; Task API accepts the task schema. Public HTTPS only,
  port 443, no private destinations or redirects; timeout and 20 MB decoded
  response limits apply. API failures never substitute sample data. Local files
  need no network. DummyJSON carts lack required sales facts and are unsupported.

Details: [data contract and aliases](docs/data-contract.md),
[Sales API contract](docs/sales-api.md).

## Design, extension and tests

`UI / CLI -> ReportService -> Readers -> validated SourceData -> Report Builder -> WordRenderer`

Readers handle formats and validation; builders use deterministic calculations
and Decimal money; the renderer preserves template branding and inserts content.
No AI, database or cloud service is needed. Report generation does not modify the
template, and changed UI inputs invalidate previous downloads.

To add a source, implement `read() -> SourceData`, reuse schemas/error boundaries,
and register it in input selection and the relevant entry point. To add a report,
implement `build(data, period) -> ReportData` and register it in the service's
builder mapping and labels. Test valid/invalid input and a final generated DOCX.
See [reader contract](docs/readers.md) and [template contract](docs/word-rendering.md).

```bash
python -m pytest -q
```

### Reports retained by tests

`python -m pytest -q` retains the 11 current-sample Word reports under
`sample_reports/Sales_Summary/<run-id>/` and
`sample_reports/Operations_KPI/<run-id>/`. Each run uses a new directory;
filenames identify the source file and format. Other edge-case test outputs
remain temporary. These are locally generated artifacts, excluded from Git.

Useful focused checks:

| Command | Purpose |
| --- | --- |
| `python -m pytest tests/test_current_samples.py -q` | Read all 11 current CSV/XLSX/PDF samples, generate Word reports, verify sales totals, task rates, charts and unchanged template |
| `python -m pytest tests/test_sales_fields.py tests/test_task_files.py -q` | Check aliases, missing/ambiguous fields, invalid dates/status and duplicate task IDs |
| `python -m pytest tests/test_data_inputs.py tests/test_api_reader.py -q` | Exercise uploads and controlled API failures, unsafe URLs, DNS pinning and no silent fallback |
| `python -m pytest tests/test_cli.py -q` | Verify non-interactive generation, exit codes, duplicate inputs and overwrite protection |

Current control totals: October sales **7,390 AUD / 5 orders**, November sales
**8,650 AUD / 5 orders**; October tasks **9 of 12 completed (75%)**, November
**7 of 10 (70%)**. Sales PDF content is October data even though its filename
includes 10-11. KPI snapshots are not filtered by the selected dates.

Tests use current `sample_data` for end-to-end checks. Fixed edge-case regression
fixtures live separately in `tests/fixtures`, so editing demo data does not change
those independent expected values. API tests use controlled responses, without
external network availability. See [verification scope](docs/testing.md).

### Current template and supplied test files

Both report types use `templates/company_template.docx`, with the official
TechInnovate logo in its original proportions, company name in the footer and
page numbers. The renderer fills seven documented anchors while preserving the
shared styles. See [current template contract](docs/word-rendering.md#template-contract).

Current test data is in `sample_data/Sales_Summary_Dummy_Data/` and
`sample_data/Operations_KPI_Dummy_Data/`. Use the sales CSV above for the offline
quick start and upload task files through the UI for offline KPI testing. Legacy
`sample_data/sales.csv`, metrics and task-fixture paths are no longer supplied;
`--tasks offline` and older fixture-based scripts require those fixtures to be
restored explicitly and are not part of the quick start. No silent fallback occurs.

Latest full verification: **320 tests passed**, with 14 existing dependency
deprecation warnings. The current quick-start CLI was also executed successfully;
its 0.84-second local generation time excludes environment setup.

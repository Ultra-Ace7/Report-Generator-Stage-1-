# TechInnovate Report Generator

Generate Sales Summary and Operations/KPI Word reports from CSV/Excel, PDF and
REST API inputs using one immutable sample company template. Python 3.9.6 is the
verified development baseline. All supplied business data is fictional.

## Quick start

From the repository directory on macOS/Linux with Python 3.9 installed:

```bash
python3.9 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python cli.py --report sales_summary --start 2026-10-01 --end 2026-10-31 --sales sample_data/sales.csv --metrics sample_data/monthly_metrics.pdf --tasks offline --output output/SalesSummary_2026-10.docx
```

Skip virtual-environment creation if you already have this project's `venv`.
Use an equivalent Python 3.9 executable if it has a different name. On Windows,
create with `py -3.9 -m venv venv` and activate with `venv\Scripts\activate` in
Command Prompt. Windows has not been tested.

Open `output/SalesSummary_2026-10.docx`: expected revenue is AUD 7,000.00,
PDF target AUD 8,000.00 and target achievement 87.5%. The offline task snapshot
contains five synthetic tasks, three completed. Existing outputs are protected;
choose a different filename when repeating the command.

Dependencies need an internet connection for installation. Offline report runs
need no network. `requirements-lock.txt` records the exact installed environment.
No database, cloud account, API key or Word installation is required to generate
DOCX. Word-compatible software is needed to view the result.

## Run the UI, live API and second report

```bash
python -m streamlit run app.py --server.address 127.0.0.1
```

Open http://127.0.0.1:8501, choose the report, sources and dates, then click
**Generate Word report** and **Download Word report**. Sample files are selected
initially. Upload mode accepts CSV/XLSX sales files and a metrics PDF following
the documented layout. Choose **Live public demo API** to call JSONPlaceholder.

For a command-line report combining all three actual source types:

```bash
python cli.py --report sales_summary --start 2026-10-01 --end 2026-10-31 --sales sample_data/sales.csv --metrics sample_data/monthly_metrics.pdf --tasks live --output output/SalesSummary_2026-10_live.docx
```

Generate the second report without UI:

```bash
python cli.py --report operations_kpi --start 2026-10-01 --end 2026-10-31 --metrics sample_data/monthly_metrics.pdf --tasks offline --output output/OperationsKPI_2026-10.docx
```

Full options, error behavior and upload limits: [running the app](docs/running-the-app.md).

## Design and rationale

`UI / CLI -> ReportService -> readers -> validated SourceData -> report builder -> WordRenderer`

- Readers use standard-library CSV, openpyxl, pdfplumber and httpx to extract data.
  They return the same Pydantic models, keeping file formats out of report logic.
- Builders calculate deterministic metrics with Decimal money arithmetic. No AI
  is necessary for reliable aggregation and rule-based summaries.
- Both entry points call one service. A future scheduler can invoke the CLI or
  service without a browser; scheduled execution itself is outside Stage 1.
- python-docx fills seven explicit template anchors and inserts dynamic tables
  and Matplotlib charts. This avoids coupling business logic to Word markup.
  Logo, styles, headers and footers are preserved, and output never overwrites
  the original template. See [template contract](docs/word-rendering.md).
- Streamlit supplies a small upload/selection/download UI without a separate
  web backend. Errors are shown to the user and logged to `logs/report_generator.log`.
- Python 3.9 follows the existing local environment. Pinned dependencies are
  tested together; pandas and docxtpl remain from the initial dependency plan
  but are not required by the current readers/renderer.

The sample template follows the permitted sample-company-template approach. Its geometric TI logo is illustrative, not official company artwork.

## Add a data source

1. Add `sources/your_reader.py` with a class implementing
   `read(self) -> SourceData` (the `DataReader` protocol in `sources/base.py`).
2. Parse input into the models in `core/schemas.py`. Wrap reads in
   `read_boundary('Your source')`; convert format-specific exceptions into
   `SourceReadError` or `DataValidationError`. Keep report calculations out of readers.
3. Pass the new reader directly to `ReportService.generate(..., readers=[...])`.
   To expose it to users, add its option in `core/input_selection.py`, `cli.py`
   and `app.py`. Existing readers/builders do not need rewriting.
4. Test valid data, malformed/missing input and at least one final DOCX run.
   See the in-memory reader extension in `tests/test_report_service.py`.

An adapter producing existing orders, targets or tasks needs no model changes.
A genuinely new business entity requires an explicit schema addition and merge
policy in `sources/base.py`; this is not automatic schema discovery.

## Add a report type

1. Add `reports/your_report.py` with `build(data: SourceData, period: DateRange)
   returning `ReportData`. Choose a lowercase underscore identifier, e.g.
   `customer_summary`. Validate required sources and define date semantics.
2. Return metrics, narrative text, tables and a `ChartSpec`. Existing chart kinds
   are `sales_trend` and `task_status`; a new chart shape needs a small explicit
   addition in `renderer/chart_builder.py` and `ChartSpec`.
3. Register the builder in `DEFAULT_BUILDERS` and its label in `REPORT_LABELS`
   in `core/report_service.py`. CLI choices and UI report choices use those labels.
   Add appropriate report-specific source/date guidance in `app.py`.
4. Alternatively inject `ReportService(builders={'customer_summary': builder})`
   for direct integration. No edits to existing report builders or Word renderer
   are needed when using the common content contract.
5. Test calculations, source requirements and generated document content. The
   extension test creates a third report through the existing pipeline.

## Data scope and limitations

- Dates filter sales inclusively. Targets are compared only for complete calendar
  months with every required target present. Partial periods show unavailable.
- JSONPlaceholder tasks are unrelated, undated demonstration snapshots. Their
  retrieval timestamp and source are printed in reports. Dates do not filter
  tasks; Operations/KPI treats the date range as context only.
- Offline mode is explicitly labelled and never silently replaces a failed API.
- PDF extraction supports the supplied text-based metrics layout, not arbitrary
  layouts or scanned documents/OCR. Excel supports `.xlsx`, not legacy `.xls`.
- Duplicate order IDs are rejected. No real customer data is included.
- Optional PDF export converts the generated Word report using LibreOffice; see
  [PDF setup and usage](docs/pdf-export.md). Scheduling, email delivery, accounts
  and cloud deployment are outside scope.

See [data contract](docs/data-contract.md), [readers](docs/readers.md) and
[calculation rules](docs/report-calculations.md).

## Tests and sample reports

```bash
python -m pytest -q
python -m pip check
python -m scripts.generate_samples
```

The last command creates both offline reports in a new timestamped `output/`
directory. Tests cover each source, calculations, template preservation, dynamic
rows, complete report generation, CLI, UI errors and downloads. API tests use
controlled responses and run without a public network service.

`sample_reports/` contains two offline DOCX examples and a live-API sales example.
All were visually checked. The live example records its own retrieval timestamp;
its task totals may differ from a future API response. `sample_data/` contains CSV,
PDF, API fixture JSON and fixture metadata. CSV satisfies the Excel/CSV source
category; XLSX behavior is additionally covered by generated test workbooks.

## Verification

Core functionality and requirement review are implemented. See
[requirements verification](docs/requirements-verification.md) for verification evidence and scope.
A fresh local Python 3.9.6 environment installed dependencies and generated its
first report in 48.35 seconds with pip caching disabled. This excludes installing
Python, downloading the repository and human reading time; see the acceptance
review for the precise scope. The clean environment also passed all 177 tests.

## Additional resilience checks

See [testing and benchmark scope](docs/testing.md) for the latest 186-case test
run, repeated-generation and session-isolation checks, and optional synthetic
performance measurements. Historical clean-install results above describe the
177-case suite that existed at the time of that verification.

## PDF download

Generate a report to prepare both formats. **Download PDF report** appears to
the right of **Download Word report**.
This optional feature requires a local LibreOffice installation; Word download
remains available if conversion fails. See [PDF export](docs/pdf-export.md) for
setup, CLI usage and verification. The latest full test run passed 196 cases.

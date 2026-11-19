# UI and command line (Step 6)

Both entry points call `ReportService.generate()`: read inputs, combine and
validate, build report content, render DOCX. Neither entry point calculates KPIs.
The service accepts reader objects and a report-builder mapping so additional
adapters/builders can be added without rewriting existing report implementations.

## Launch the local interface

From the project directory:

```bash
source venv/bin/activate
python -m streamlit run app.py --server.address 127.0.0.1
```

Open http://127.0.0.1:8501. Both report types use the bundled immutable company template.

## Data Inputs workflow

Choose a report type and date range, then configure **Data Inputs**:

- **Upload Files** enables local input. **Use bundled sample files** loads
  `sales.csv` and `monthly_metrics.pdf` for a quick demonstration. Clear that
  checkbox to use one multi-file upload widget accepting `.csv`, `.xlsx`, `.pdf`.
- **Fetch from REST API** independently enables a live request. Its URL defaults
  to `https://jsonplaceholder.typicode.com/todos`. It can be used with files or
  alone for Operations/KPI. Fetching occurs only on generation.
- **Offline Sample Task Data** is a separate, explicitly labelled five-task
  fixture, selected initially for the offline demo. It is available when API
  fetching is disabled. An API failure never automatically loads this fixture.

To demonstrate all three actual source types, select Sales Summary, upload the
sample sales CSV (or XLSX) and metrics PDF together, and enable **Fetch from REST
API**. Generate once: sales amounts, PDF targets and a live task overview appear
in the same report. Bundled sample files can also be combined with the live API.
Offline fixture data alone is not evidence of a real REST request.

For file-only processing, leave **Upload Files** enabled, disable API fetching
and clear **Offline Sample Task Data**. No network is used. For API-only
Operations/KPI, disable **Upload Files** and enable the API option.

| Report | Required input | Optional input |
| --- | --- | --- |
| Sales Summary | Valid CSV/XLSX sales with orders in the selected period | PDF sales targets; API or offline task overview |
| Operations/KPI | API tasks or explicit offline task fixture | PDF completion benchmark; sales files are validated if supplied but do not affect task KPIs |

Dates filter sales inclusively. Monthly targets require complete months and all
corresponding targets. Tasks have no historical dates: their snapshot is labelled
with source, retrieval time and mode, and is not filtered by the selected dates.
Missing data does not become a fabricated zero or other invented metric.

### File validation and multiple-file policy

Each file is limited to 20 MB and saved under a generated temporary name. Suffixes
route inputs; readers then validate actual contents and the documented schemas.
Temporary inputs and outputs are removed after generation. Changing any effective
input invalidates the previous download.

- CSV: UTF-8 (optional BOM), required fields `order_id`, `order_date`, `customer`,
  `service`, `revenue`, `currency`; documented aliases and unrelated extra columns
  are supported, and column order can vary. See the
  [data contract](data-contract.md) for value and currency rules.
- XLSX: the same sales columns; values-only cells, no formulas or error cells.
  **Excel worksheet name (optional)** appears only for XLSX uploads. Blank uses
  each workbook's first worksheet; a name applies to every uploaded workbook.
  A missing named worksheet fails clearly. CSV and PDF have no worksheet field.
- PDF: text extraction from the documented monthly-metrics layout only; scanned
  PDFs, arbitrary layouts, corrupt files and invalid targets are rejected.
- Multiple CSV/XLSX files are combined. Duplicate order IDs are rejected rather
  than double-counted. At most one PDF is accepted; multiple PDFs are rejected
  because target/benchmark selection would otherwise be ambiguous.

### Compatible API and network safeguards

The response must be a nonempty JSON array. Every object must contain exactly
`userId` (positive integer), `id` (unique positive integer), `title` (nonempty
string) and `completed` (JSON boolean). Extra/missing keys, duplicate IDs, wrong
types and arbitrary unrelated API schemas are rejected. Example:

```json
[{"userId": 1, "id": 1, "title": "Prepare report", "completed": true}]
```

Only public HTTPS URLs on port 443 are accepted, without credentials or fragments.
Local/internal hostnames and nonpublic literal IPs are blocked. Before connecting,
all resolved addresses must be public; the transport pins one validated address
while preserving the original Host and TLS certificate hostname. This avoids a
second hostname resolution changing the destination. Redirects and environment
proxies are disabled. The default HTTPX timeout is 10 seconds per network
operation, not an overall deadline; operating-system DNS resolution has its own
timeout. The adapter does not provide authentication or arbitrary schema mapping.
Injected clients are a trusted developer/test extension point; the UI always uses
the protected transport. Never inject an untrusted client into this pipeline.

HTTP errors, timeouts, connection failures, invalid JSON and incompatible records
show an error and leave no successful report download. Correct the input and
regenerate; no automatic offline substitution occurs.

Click **Generate Word report** and download the result. Optional PDF conversion
runs automatically; **Download PDF report** stays to the right of **Download Word
report**. Word remains available if PDF conversion is unavailable.

## CLI examples

Offline sales report with all sample inputs:

```bash
python cli.py --report sales_summary --start 2026-10-01 --end 2026-10-31 \
  --sales sample_data/sales.csv --metrics sample_data/monthly_metrics.pdf \
  --tasks offline --output output/sales_october.docx
```

Use `--tasks live` for a real REST API call. To generate an operations report with
only the task source:

```bash
python cli.py --report operations_kpi --start 2026-10-01 --end 2026-10-31 \
  --tasks offline --output output/operations_snapshot.docx
```

Repeat `--sales` for multiple non-overlapping sales files. `--sheet` changes the
Excel sheet; `--template` selects a compatible template with the required anchors.
An existing output is never overwritten: use a new filename. Input paths and the
output path are relative to your shell directory; the default template and offline
fixture paths are anchored to the application directory. `python cli.py --help`
lists all arguments. Exit code 0 means success, 1 means generation/input failure,
and 2 means malformed command-line arguments. No prompts or UI are required.

## Errors and logs

User-facing failures include missing files, unsupported formats, bad fields,
duplicate orders, empty sales date ranges, reversed dates, absent task snapshots,
API failures, bad templates and output conflicts. Logs are written to
`logs/report_generator.log`. Streamlit reruns reuse the same file handler.
Unexpected pipeline errors are logged with details and surfaced as a short error
instead of leaking a traceback into the interface.

Automated tests exercise the service, CLI and Streamlit AppTest workflows. API
failure tests use MockTransport or injected failures; they do not depend on the
public service. Upload tests supply in-memory CSV/PDF files to the actual UI
processing path. Browser download delivery is also checked separately in the
running application.

## Step 6 verification

- Python 3.9.6: 174 tests passed; 14 dependency deprecation warnings.
- Installed dependencies passed `pip check`.
- A real browser generated and downloaded the offline sales report; the downloaded
  DOCX was reopened and its tables, revenue and chart were verified.
- The CLI generated `sample_reports/SalesSummary_2026-10_live_demo.docx` using
  CSV, PDF and a real REST API response. Both rendered pages were visually reviewed.
  Its API snapshot contains 200 demonstration tasks, with 90 completed. The embedded
  snapshot timestamp records when the data was retrieved; it is not historical
  sales-period data.

## References

- Streamlit downloads: https://docs.streamlit.io/1.40.0/develop/api-reference/widgets/st.download_button
- Streamlit application tests: https://docs.streamlit.io/develop/api-reference/app-testing

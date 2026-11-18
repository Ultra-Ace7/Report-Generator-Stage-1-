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

Open http://127.0.0.1:8501. Select report type, one or more sources, sample or
uploaded files, task mode, and date range. Click **Generate Word report**, review
the result summary and download the DOCX. Both report types use the bundled
company template. The UI does not modify it.

Sample mode uses sales.csv and monthly_metrics.pdf. Upload mode accepts multiple
CSV/XLSX sales files and one PDF in the documented layout. Excel defaults to the
Sales worksheet; change the worksheet field if needed. Individual uploaded files
are limited to 20 MB. Temporary inputs and output are removed after generation;
only the generated download bytes remain in the current UI session. Changing any
input clears the previous result so a stale download is not presented as current.

Offline tasks use the explicit fixture. Live tasks call JSONPlaceholder on each
generation; a failed call displays an error and never substitutes fixture data.
Sales Summary requires sales records; targets and task overview are optional.
Operations/KPI requires tasks, with an optional PDF benchmark; sales are not used
in task calculations. Dates do not filter undated task snapshots.

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

# Requirements verification

Implementation evidence for Stage 1, using a sample company template and
demonstration data. Known limitations are stated alongside verification results.

| Requirement | Implementation and evidence | Status |
| --- | --- | --- |
| Excel/CSV input | CsvExcelReader, strict CSV and XLSX validation, source tests | Pass |
| PDF input | PdfMetricsReader extracts sample text-based metrics PDF | Pass within documented layout |
| REST API | ApiTaskReader calls JSONPlaceholder with timeout and error handling; live sample exists | Pass |
| Easy extension | DataReader and ReportBuilder protocols, injectable builder registry; third-type end-to-end extension test | Pass |
| At least two report types | Sales Summary and Operations/KPI | Pass |
| One original template | Both use templates/company_template.docx | Pass |
| Branding retained; original immutable | Tests compare template hash and header/footer/styles/logo bytes | Pass |
| Text, variable rows, chart | Both reports contain narrative, dynamic tables and one chart; 200-row structural test | Pass |
| Choose type, sources and date range | Streamlit Data Inputs controls (independent files/API), report/date controls and unchanged CLI arguments | Pass |
| DOCX with clear filename | UI derives filename from type/dates/mode; CLI accepts destination | Pass |
| Clear errors and logs | Bad inputs/API errors reach UI and log; no silent fallback; bad-upload recovery test | Pass |
| UI-independent generation | CLI and UI use ReportService | Pass |
| Dummy data only | Fictional sales/targets and public demo tasks | Pass |
| Tests for every source and full report | Reader, report, template, service, CLI and UI tests | Pass |
| All three sources in one report | Live sales sample includes sales, PDF target and separately labelled API tasks; controlled-response final DOCX assertions | Pass |
| README setup/run/design/extension | Quick start, rationale and both extension recipes documented in README | Implemented |
| Sample source files | CSV, PDF and API JSON fixture plus metadata | Pass |
| Two generated sample reports | Two offline samples plus one live-API sales sample | Pass |
| New reader generates within ten minutes | Fresh Python 3.9.6 venv, uncached install and first CLI report: 48.35 seconds | Local automated setup passed; see timing scope below |
| PDF export | Local LibreOffice conversion, UI download and CLI export; two PDF samples | Implemented; optional dependency |
| Scheduling/email/accounts/cloud | Explicitly Stage 2/out of scope | Intentionally absent |

## Verification evidence

Full suite: 177 tests passed on Python 3.9.6, with 14 third-party
deprecation warnings. `pip check` found no broken requirements.

Automated checks exercise bad files, failed APIs, input errors, template
immutability and variable-length tables. Visual inspection in the preceding
stage covered both offline reports, both pages of the live sales report, and
multi-page table pagination. Browser download was separately verified by
reopening the downloaded DOCX. The optional application PDF export and its separate verification are described
in [PDF export](pdf-export.md). Earlier QA renders were only inspection artifacts.

## Fresh-environment verification (18 November 2026)

Exported source with the application implementation at `c2aa782` into an isolated temporary directory,
created a new Python 3.9.6 virtual environment without system packages, and ran
the README installation and first-report commands using that interpreter.
Dependency installation used `--no-cache-dir`; the existing project venv was not
reused. The README permits an equivalent Python 3.9 executable name.

| Stage | Wall-clock seconds | Result |
| --- | ---: | --- |
| Create environment | 1.69 | Pass |
| Download/install requirements | 30.81 | Pass |
| Generate first sales report | 15.84 | Pass |
| Setup through first report, including orchestration overhead | 48.35 | Below ten minutes |
| Check installed dependency compatibility | 0.48 | No broken requirements |
| Complete automated suite | 13.90 | 177 passed, 14 dependency warnings |
| Generate second report | 0.67 | Pass |

Machine-readable timings: [clean-install-results.json](clean-install-results.json).
This verifies the automated setup on the development Mac with Python already
installed. It excludes repository download, Python installation, human reading
and Word viewing time. It is not an independent novice usability study or a
cross-platform guarantee. Both report outputs were reopened and their expected
metrics and preserved branding checked.

## Input workflow regression

The 19 November 2026 Data Inputs update passed all 237 tests and a real API
source check. See [current verification evidence](testing.md#data-inputs-refactor-verification--19-november-2026).
Earlier timings and counts above remain historical measurements.

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
| Choose type, sources and date range | Streamlit controls and CLI arguments | Pass |
| DOCX with clear filename | UI derives filename from type/dates/mode; CLI accepts destination | Pass |
| Clear errors and logs | Bad inputs/API errors reach UI and log; no silent fallback; bad-upload recovery test | Pass |
| UI-independent generation | CLI and UI use ReportService | Pass |
| Dummy data only | Fictional sales/targets and public demo tasks | Pass |
| Tests for every source and full report | Reader, report, template, service, CLI and UI tests | Pass |
| All three sources in one report | Live sales sample includes sales, PDF target and separately labelled API tasks; controlled-response final DOCX assertions | Pass |
| README setup/run/design/extension | Quick start, rationale and both extension recipes documented in README | Implemented |
| Sample source files | CSV, PDF and API JSON fixture plus metadata | Pass |
| Two generated sample reports | Two offline samples plus one live-API sales sample | Pass |
| New reader generates within ten minutes | Quick-start command available; existing-environment smoke run only | Clean first-time install timing pending |
| PDF export | Optional bonus, not implemented | Not required |
| Scheduling/email/accounts/cloud | Explicitly Stage 2/out of scope | Intentionally absent |

## Verification evidence

Full suite: 177 tests passed on Python 3.9.6, with 14 third-party
deprecation warnings. `pip check` found no broken requirements.

Automated checks exercise bad files, failed APIs, input errors, template
immutability and variable-length tables. Visual inspection in the preceding
stage covered both offline reports, both pages of the live sales report, and
multi-page table pagination. Browser download was separately verified by
reopening the downloaded DOCX. The optional PDF QA renders are not an application
PDF-export feature.

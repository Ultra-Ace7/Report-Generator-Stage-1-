# Word template and rendering (Step 5)

## Generate sample reports

```bash
python -m scripts.generate_samples
```

This reads the sales CSV, metrics PDF and explicit offline task fixture, builds
both report types and creates DOCX files under a new `output/samples_<timestamp>`
directory. It uses the existing `templates/company_template.docx` and never
rebuilds or saves over it. Use `--output-dir <directory>` to choose a destination;
existing report filenames are rejected rather than overwritten.

The supplied October examples use synthetic data and an offline task snapshot.
They demonstrate document generation, not a live API run. The additional
`SalesSummary_2026-10_live_demo.docx` example was generated through the CLI using
a real API response together with CSV and PDF inputs, and visually reviewed.

## Template contract

Both report types use the same A4 company template. It contains a sample TI logo,
Arial styles, a persistent page header, footer page numbering and these exact
standalone paragraph anchors, each appearing once:

- `[[TITLE]]`
- `[[PERIOD]]`
- `[[SUMMARY]]`
- `[[METRICS]]`
- `[[CHART]]`
- `[[DETAILS]]`
- `[[NOTES]]`

Keep the template's named styles `Report Table`, `Report Table Text` and
`Report Note`. Report headings and paragraphs inherit the original styles.
Dynamic tables use repeated header rows, deliberate widths, automatic row heights,
light borders and alternating shading. Sales and task details retain every row.
Long documents paginate naturally; the executive section and supporting detail
start on separate pages. The template's source file is immutable during rendering.

`WordRenderer(template).render(report, output_path)` loads template bytes into
memory and fills only the known anchors. It uses python-docx for paragraphs,
variable-length tables and embedded PNG charts. This concrete anchor contract is
simpler than mixing Jinja loops and OOXML table manipulation for this small app;
docxtpl remains installed from the original plan but is not needed by this renderer.
The renderer accepts either report's shared ReportData model, with no file-reader
or business-calculation logic.

Missing/damaged templates, missing or duplicate anchors, missing styles,
unsupported destination extensions and existing destinations raise RenderingError
(a ReportError subtype). Direct template paths and symlink aliases cannot be
used as report destinations. Rendering errors are logged.

## Template creation versus report generation

`scripts/create_template.py` creates the initial sample template and refuses to
overwrite an existing file. Normal report generation never invokes it. For an
intentional redesign, call its `create_template(new_path)` function to produce a
separate candidate, then validate that candidate before adopting it. The sample
logo is a simple geometric mark created for this task, not the company's official
branding. No external design assets or AI model are required.

## Verification

Automated tests compare the template's SHA-256 before and after each report run;
header, footer, styles and embedded logo bytes also match the resulting reports.
Tests check report text, exact table values, all 200 stress-test task rows, repeated
table-header properties, embedded chart, special XML characters, missing/corrupt
templates and overwrite protection.

Visual QA uses a separate document-rendering toolchain, not an application
runtime dependency. PDF/PNG renders are temporary QA artifacts; the requested
outputs are DOCX. Visual review checks both sample reports and a multi-page task
table. Word versions and installed fonts can change pagination slightly.

The two reviewed examples are retained in `sample_reports/` for Git submission; generated runs under `output/` remain ignored. The original template and
both sample reports were visually checked page by page. Both examples are two
pages; a 40-task pagination test is three pages with a repeated table header.

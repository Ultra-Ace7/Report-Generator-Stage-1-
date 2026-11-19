# Word template and rendering (Step 5)

## Generate a report from current samples

```bash
python cli.py --report sales_summary --start 2026-10-01 --end 2026-10-31 --sales sample_data/Sales_Summary_Dummy_Data/sales_2026-10.csv --output output/template_check.docx
```

Use a new output filename for each run. Earlier sample-generation scripts and
historical reports referenced below used fixtures that are no longer bundled.
Normal generation uses the existing template and never recreates it.

## Template contract

Both report types use the same A4 company template. It contains the official TechInnovate logo downloaded from the company website,
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
separate candidate, then validate that candidate before adopting it. The logo is loaded from `templates/assets/techinnovate-logo.png` with its original
proportions; its official source is recorded in `templates/assets/SOURCE.md`.
The footer shows TechInnovate and the page number. These are demonstration
reports, not company-issued documents. No AI model is required.

## Verification scope

Automated tests compare the template's SHA-256 before and after each report run;
header, footer, styles and embedded logo bytes also match the resulting reports.
Tests check report text, exact table values, all 200 stress-test task rows, repeated
table-header properties, embedded chart, special XML characters, missing/corrupt
templates and overwrite protection.

Visual QA uses a separate document-rendering toolchain, not an application
runtime dependency. PDF/PNG renders are temporary QA artifacts; the requested
outputs are DOCX. Visual review checks both sample reports and a multi-page task
table. Word versions and installed fonts can change pagination slightly.

Earlier reviewed examples used the previous sample template and are no longer bundled; generated runs under `output/` remain ignored. The original template and
both sample reports were visually checked page by page. Both examples are two
pages; a 40-task pagination test is three pages with a repeated table header.

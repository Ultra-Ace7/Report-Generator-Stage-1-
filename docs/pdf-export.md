# Optional PDF export

The Word report remains the primary output. PDF export converts those exact DOCX
bytes locally using LibreOffice; it does not fetch the API again or recalculate
metrics. No document is uploaded to an external conversion service.

## UI

Generate a report once. Word and PDF are prepared together; download buttons
appear side by side, with **Download PDF report** on the right.
The prepared PDF is cached alongside the Word bytes in the current session.
Changing inputs clears both results. Conversion errors show a warning while
keeping Word download available and disabling the PDF download. Generate again
to retry after resolving the problem.

## Setup

Install LibreOffice separately; it is not a pip dependency. The application looks
for `soffice` / `libreoffice` on PATH, the standard macOS application path, or a
Windows LibreOffice installation under Program Files. For a custom installation,
set `LIBREOFFICE_PATH` to the executable before launching the app, for example:

```bash
export LIBREOFFICE_PATH='/Applications/LibreOffice.app/Contents/MacOS/soffice'
python -m streamlit run app.py --server.address 127.0.0.1
```

An optional machine-local `.pdf-converter-path` file in the project root may
contain the executable's absolute path. It is ignored by Git and must not be
copied from another machine. Environment configuration takes precedence. Do not
put command arguments in either setting. A configured but invalid path produces
an explicit setup error rather than silently selecting a different executable.

DOCX-only generation needs no LibreOffice. PDF output may paginate differently
when fonts or converter versions differ; review examples on the target machine.
Windows discovery is implemented but has not been verified on Windows.

## Command line

```bash
python -m scripts.export_pdf sample_reports/SalesSummary_2026-10_offline_demo.docx output/SalesSummary_2026-10.pdf
```

Use a new destination: existing files are never overwritten. The command returns
0 on success, 1 on an export/input error, and 2 for invalid command syntax.

Each conversion uses a separate temporary directory and LibreOffice profile,
passes arguments without a shell, limits the subprocess to 60 seconds, and checks
that a readable PDF with at least one page was produced. Temporary input/output
is cleaned up after bytes are loaded. Source DOCX and template are unchanged.

## Verification

Ten automated cases cover converter arguments/profile separation, subprocess
failure, timeout, missing/invalid output, permission failure, invalid configured
path, UI success/invalidation, UI failure/regeneration and CLI overwrite protection.
The full suite passed 196 cases on Python 3.9.6 (14 dependency warnings).

A real browser download was also verified. Both offline report types were converted with the real local converter. Their
PDF text, key metrics and two-page layouts were checked, including all four pages
visually. Two PDF examples are included alongside the DOCX samples.

Conversion flags follow the [LibreOffice command-line documentation](https://help.libreoffice.org/latest/en-GB/text/shared/guide/start_parameters.html).

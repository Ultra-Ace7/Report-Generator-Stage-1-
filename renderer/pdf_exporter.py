"""Optional local DOCX-to-PDF conversion with an isolated LibreOffice profile."""
from io import BytesIO
import logging
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

import pdfplumber

from core.exceptions import ReportError

logger = logging.getLogger('report_generator.pdf')
LOCAL_CONFIG = Path(__file__).resolve().parents[1] / '.pdf-converter-path'


class PdfExportError(ReportError):
    """PDF export failed; the original Word result remains usable."""


def find_converter():
    configured = os.environ.get('LIBREOFFICE_PATH')
    if not configured and LOCAL_CONFIG.exists():
        configured = LOCAL_CONFIG.read_text(encoding='utf-8').strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate.resolve())
        raise PdfExportError('The configured LibreOffice executable is unavailable. Check the PDF export setup.')
    for name in ('soffice', 'libreoffice'):
        executable = shutil.which(name)
        if executable:
            return executable
    candidates = [Path('/Applications/LibreOffice.app/Contents/MacOS/soffice')]
    for variable in ('PROGRAMFILES', 'PROGRAMFILES(X86)'):
        if os.environ.get(variable):
            candidates.append(Path(os.environ[variable]) / 'LibreOffice/program/soffice.exe')
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise PdfExportError('PDF export requires LibreOffice. Install it or set LIBREOFFICE_PATH; Word download is still available.')


def export_pdf(docx_bytes):
    """Convert the existing report bytes, without fetching sources again."""
    try:
        executable = find_converter()
        with TemporaryDirectory(prefix='report-pdf-') as directory:
            root = Path(directory)
            source = root / 'report.docx'
            source.write_bytes(docx_bytes)
            output = root / 'converted'
            output.mkdir()
            profile = (root / 'profile').as_uri()
            result = subprocess.run([executable, '-env:UserInstallation=' + profile,
                '--headless', '--convert-to', 'pdf:writer_pdf_Export', '--outdir', str(output), str(source)],
                capture_output=True, timeout=60, check=False)
            pdf = output / 'report.pdf'
            if result.returncode != 0 or not pdf.is_file():
                raise PdfExportError('PDF conversion did not produce a report. Retry or download the Word version.')
            data = pdf.read_bytes()
            try:
                if not data.startswith(b'%PDF-'):
                    raise ValueError('Not a PDF')
                with pdfplumber.open(BytesIO(data)) as document:
                    if not document.pages:
                        raise ValueError('Empty PDF')
            except Exception as exc:
                raise PdfExportError('The converted PDF is invalid. Retry or download the Word version.') from exc
            logger.info('PDF export completed')
            return data
    except subprocess.TimeoutExpired as exc:
        logger.error('PDF conversion timed out')
        raise PdfExportError('PDF conversion timed out. Retry or download the Word version.') from exc
    except OSError as exc:
        logger.error('Cannot run PDF conversion: %s', type(exc).__name__)
        raise PdfExportError('Cannot run PDF conversion. Check LibreOffice and file permissions; Word download is still available.') from exc
    except PdfExportError as exc:
        logger.error('PDF export failed: %s', exc)
        raise

"""Export an existing Word report: python -m scripts.export_pdf INPUT.docx OUTPUT.pdf."""
import argparse
from pathlib import Path
import sys

from core.logging_config import configure_logging
from renderer.pdf_exporter import export_pdf, PdfExportError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args(argv)
    try:
        configure_logging()
        if args.source.suffix.lower() != '.docx' or args.output.suffix.lower() != '.pdf':
            raise PdfExportError('Use a .docx source and a .pdf destination.')
        if args.output.exists():
            raise PdfExportError('PDF destination already exists. Choose a new filename.')
        data = export_pdf(args.source.read_bytes())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write(data)
    except (PdfExportError, OSError) as exc:
        print('PDF export failed: {}'.format(exc), file=sys.stderr)
        return 1
    print('PDF saved: {}'.format(args.output.resolve()))
    return 0


if __name__ == '__main__':
    sys.exit(main())

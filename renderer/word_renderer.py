"""Fill known template anchors without changing the original template file."""
from io import BytesIO
import logging
from pathlib import Path
import re

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, RGBColor

from core.exceptions import ReportError
from renderer.chart_builder import render_chart

logger = logging.getLogger('report_generator.renderer')
MARKERS = ('TITLE', 'PERIOD', 'SUMMARY', 'METRICS', 'CHART', 'DETAILS', 'NOTES')


class RenderingError(ReportError):
    """The supplied template or destination cannot produce a report."""


def replace_text(paragraph, text):
    # Keep paragraph style and the first run's template formatting.
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ''
    else:
        paragraph.add_run(text)


def remove(paragraph):
    paragraph._p.getparent().remove(paragraph._p)


def column_weights(columns):
    weights = []
    for title in columns:
        if title in ('Task', 'Service', 'Customer'):
            weights.append(3.5 if title == 'Task' else 2.0)
        elif title in ('Order ID', 'Task ID', 'User ID', 'Status'):
            weights.append(1.0)
        elif title == 'Date':
            weights.append(1.3)
        elif title == 'Metric':
            weights.append(3.3)
        else:
            weights.append(1.5)
    return weights


def insert_table(document, anchor, columns, rows, width):
    table = document.add_table(rows=1, cols=len(columns))
    table.style = 'Report Table'
    table.autofit = False
    anchor._p.addprevious(table._tbl)
    weights = column_weights(columns)
    widths = [int(width * weight / sum(weights)) for weight in weights]
    for column, cell_width in zip(table.columns, widths):
        column.width = cell_width
    header_property = OxmlElement('w:tblHeader')
    table.rows[0]._tr.get_or_add_trPr().append(header_property)
    for row_index, values in enumerate([columns] + list(rows)):
        is_header = row_index == 0
        row = table.rows[0] if is_header else table.add_row()
        for index, (cell, text) in enumerate(zip(row.cells, values)):
            cell.width = widths[index]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            paragraph = cell.paragraphs[0]
            paragraph.style = document.styles['Report Table Text']
            paragraph.paragraph_format.keep_with_next = is_header
            paragraph.paragraph_format.keep_together = False
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            if columns[index] in ('Date', 'Status', 'Task ID', 'User ID'):
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif columns[index] in ('Value', 'Revenue (AUD)'):
                paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run = paragraph.add_run(str(text))
            shading = OxmlElement('w:shd')
            shading.set(qn('w:fill'), '163D52' if is_header else ('F1F5F9' if len(table.rows) % 2 == 0 else 'FFFFFF'))
            cell._tc.get_or_add_tcPr().append(shading)
            if is_header:
                run.bold = True
                run.font.color.rgb = RGBColor(255, 255, 255)
    return table


class WordRenderer:
    def __init__(self, template_path):
        self.template_path = Path(template_path)

    def render(self, report, output_path):
        output_path = Path(output_path)
        try:
            if output_path.suffix.lower() != '.docx':
                raise RenderingError('Report destination must use .docx.')
            if output_path.resolve() == self.template_path.resolve():
                raise RenderingError('Report destination must not be the original template.')
            if output_path.exists():
                raise RenderingError('Report destination already exists. Choose a new filename.')
            try:
                template_bytes = self.template_path.read_bytes()
                document = Document(BytesIO(template_bytes))
            except Exception as exc:
                raise RenderingError('Cannot open Word template; check that it is a valid .docx file.') from exc
            anchors = {}
            for name in MARKERS:
                matches = [p for p in document.paragraphs if p.text == '[[' + name + ']]']
                if len(matches) != 1:
                    raise RenderingError('Template requires exactly one standalone [[{}]] anchor.'.format(name))
                anchors[name] = matches[0]
            for name in ('Report Table', 'Report Table Text', 'Report Note'):
                if name not in document.styles:
                    raise RenderingError('Template is missing required style: {}.'.format(name))
            width = document.sections[0].page_width - document.sections[0].left_margin - document.sections[0].right_margin
            title = ' '.join(re.sub(r'[^\w\s]', '', report.title).split())
            replace_text(anchors['TITLE'], title)
            replace_text(anchors['PERIOD'], report.period_label)
            replace_text(anchors['SUMMARY'], report.summary)
            insert_table(document, anchors['METRICS'], ('Metric', 'Value'), tuple((m.label, m.display) for m in report.metrics), width)
            remove(anchors['METRICS'])
            replace_text(anchors['CHART'], '')
            chart = anchors['CHART'].add_run().add_picture(BytesIO(render_chart(report.chart)), width=width)
            chart._inline.docPr.set('descr', report.chart.title + '. ' + report.chart.caption)
            for detail in report.tables:
                anchors['DETAILS'].insert_paragraph_before(detail.title, style='Heading 2')
                insert_table(document, anchors['DETAILS'], detail.columns, detail.rows, width)
            remove(anchors['DETAILS'])
            for note in report.notes:
                anchors['NOTES'].insert_paragraph_before(note, style='Report Note')
            remove(anchors['NOTES'])
            document.core_properties.title = title
            document.core_properties.subject = report.period_label
            result = BytesIO()
            document.save(result)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also protects existing files and symlink aliases.
            with output_path.open('xb') as stream:
                stream.write(result.getvalue())
            logger.info('Generated %s', output_path.name)
            return output_path
        except RenderingError as exc:
            logger.error('Word generation failed: %s', exc)
            raise
        except OSError as exc:
            logger.error('Cannot write Word report destination')
            raise RenderingError('Cannot write Word report; check the destination and permissions.') from exc

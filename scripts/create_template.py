"""Create the sample template explicitly; generation never calls this script."""
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]


def create_template(path):
    path = Path(path)
    if path.exists():
        raise FileExistsError("Template already exists; choose a new path to create a revised template.")
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    section.top_margin, section.bottom_margin = Mm(19), Mm(17)
    section.left_margin = section.right_margin = Mm(18)
    section.header_distance = section.footer_distance = Mm(8)
    for name in ("Normal", "Title", "Subtitle", "Heading 1", "Heading 2", "Header", "Footer"):
        style = doc.styles[name]
        style.font.name = "Arial"
        style.font.color.rgb = RGBColor(0, 0, 0)
        for border in style.element.xpath('./w:pPr/w:pBdr'):
            border.getparent().remove(border)
        for fonts in style.element.xpath('./w:rPr/w:rFonts'):
            for key in ('asciiTheme', 'hAnsiTheme', 'eastAsiaTheme', 'cstheme'):
                fonts.attrib.pop(qn('w:' + key), None)
    normal = doc.styles['Normal']
    normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.08
    doc.styles['Title'].font.size = Pt(25)
    doc.styles['Title'].paragraph_format.space_after = Pt(6)
    doc.styles['Heading 1'].font.size = Pt(13)
    doc.styles['Heading 1'].paragraph_format.space_before = Pt(12)
    doc.styles['Heading 1'].paragraph_format.space_after = Pt(6)
    doc.styles['Heading 2'].font.size = Pt(11)
    doc.styles['Heading 2'].paragraph_format.space_before = Pt(10)
    doc.styles['Heading 2'].paragraph_format.space_after = Pt(5)
    for name, size in (("Report Table Text", 9), ("Report Note", 9), ("Report Period", 9)):
        style = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        style.base_style = normal
        style.font.size = Pt(size)
        style.paragraph_format.space_after = Pt(4)
        style.paragraph_format.line_spacing = 1.05
    table_style = doc.styles.add_style('Report Table', WD_STYLE_TYPE.TABLE)
    table_style.base_style = doc.styles['Table Grid']
    table_style.font.name = 'Arial'
    table_style.font.size = Pt(9)
    properties = OxmlElement('w:tblPr')
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        element = OxmlElement('w:' + edge)
        for key, value in [('val', 'single'), ('sz', '4'), ('color', 'D9D9D9')]:
            element.set(qn('w:' + key), value)
        borders.append(element)
    properties.append(borders)
    margins = OxmlElement('w:tblCellMar')
    for edge in ('top', 'left', 'bottom', 'right'):
        element = OxmlElement('w:' + edge)
        element.set(qn('w:w'), '80')
        element.set(qn('w:type'), 'dxa')
        margins.append(element)
    properties.append(margins)
    table_style.element.append(properties)
    logo_path = ROOT / 'templates' / 'assets' / 'techinnovate-logo.png'
    header = section.header.paragraphs[0]
    header.add_run().add_picture(str(logo_path), width=Inches(1.9))
    header.add_run('   |   Business performance reports').font.size = Pt(9)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run('TechInnovate  |  Page ').font.size = Pt(8)
    field = OxmlElement('w:fldSimple')
    field.set(qn('w:instr'), 'PAGE')
    footer._p.append(field)
    doc.add_paragraph('[[TITLE]]', 'Title')
    doc.add_paragraph('[[PERIOD]]', 'Report Period')
    doc.add_paragraph('Prepared for management review using demonstration data.', 'Report Note')
    doc.add_paragraph('Executive summary', 'Heading 1')
    doc.add_paragraph('[[SUMMARY]]')
    doc.add_paragraph('Key indicators', 'Heading 1')
    doc.add_paragraph('[[METRICS]]')
    doc.add_paragraph('Performance chart', 'Heading 1')
    doc.add_paragraph('[[CHART]]')
    p = doc.add_paragraph('Supporting detail', 'Heading 1')
    p.paragraph_format.page_break_before = True
    doc.add_paragraph('[[DETAILS]]')
    doc.add_paragraph('Data scope and interpretation', 'Heading 1')
    doc.add_paragraph('[[NOTES]]')
    doc.core_properties.author = 'TechInnovate'
    doc.core_properties.title = 'Company report template'
    doc.core_properties.subject = 'Shared template for sales and operations reports'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        doc.save(stream)
    return path


if __name__ == '__main__':
    print(create_template(ROOT / 'templates' / 'company_template.docx'))

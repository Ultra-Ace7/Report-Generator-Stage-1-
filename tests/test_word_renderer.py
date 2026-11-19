from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from docx import Document
import pytest

from core.schemas import DateRange, SourceData, Task, TaskSnapshot
from renderer.word_renderer import RenderingError, WordRenderer
from reports.sales_summary import SalesSummaryBuilder
from reports.operations_kpi import OperationsKpiBuilder
from sources.csv_excel import CsvExcelReader
from sources.pdf_reader import PdfMetricsReader
from sources.api_reader import OfflineTaskReader
from sources.base import merge_sources

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'templates' / 'company_template.docx'
PERIOD = DateRange(start='2026-10-01', end='2026-10-31')


@pytest.fixture
def reports():
    samples = ROOT / 'tests' / 'fixtures'
    data = merge_sources(CsvExcelReader(samples / 'sales.csv').read(), PdfMetricsReader(samples / 'monthly_metrics.pdf').read(),
                         OfflineTaskReader(samples / 'todos_fixture.json', samples / 'todos_fixture_metadata.json').read())
    return [SalesSummaryBuilder().build(data, PERIOD), OperationsKpiBuilder().build(data, PERIOD)]


def test_both_reports_preserve_template_branding_and_contain_all_rows(tmp_path, reports):
    original = TEMPLATE.read_bytes()
    digest = sha256(original).hexdigest()
    for report in reports:
        output = WordRenderer(TEMPLATE).render(report, tmp_path / (report.report_type + '.docx'))
        doc = Document(output)
        text = '\n'.join(p.text for p in doc.paragraphs)
        assert report.summary in text
        assert '[[TITLE]]' not in text
        assert len(doc.inline_shapes) == 1  # Body chart; logo is in the header.
        assert len(doc.tables) == 1 + len(report.tables)
        assert len(doc.tables[0].rows) == len(report.metrics) + 1
        for actual, expected in zip(doc.tables[1:], report.tables):
            assert len(actual.rows) == len(expected.rows) + 1
            assert tuple(cell.text for cell in actual.rows[0].cells) == expected.columns
            assert tuple(tuple(cell.text for cell in row.cells) for row in actual.rows[1:]) == expected.rows
            assert actual.rows[0]._tr.xpath('./w:trPr/w:tblHeader')
        with ZipFile(BytesIO(original)) as source, ZipFile(output) as result:
            for part in ('word/header1.xml', 'word/footer1.xml', 'word/styles.xml', 'word/media/image1.png'):
                assert source.read(part) == result.read(part)
            assert len([name for name in result.namelist() if name.startswith('word/media/')]) == 2
        assert sha256(TEMPLATE.read_bytes()).hexdigest() == digest


def test_large_dynamic_table_keeps_all_tasks(tmp_path):
    snapshot = TaskSnapshot(tasks=[Task(task_id=i, user_id=1, title='Task {} with details'.format(i), completed=i % 2 == 0) for i in range(1, 201)],
                            source='Synthetic stress test', mode='offline_fixture', captured_at='2026-11-17T09:00:00+11:00')
    report = OperationsKpiBuilder().build(SourceData(snapshot=snapshot), PERIOD)
    output = WordRenderer(TEMPLATE).render(report, tmp_path / 'many.docx')
    doc = Document(output)
    assert len(doc.tables[-1].rows) == 201
    assert doc.tables[-1].rows[-1].cells[0].text == '200'


def test_xml_characters_and_unicode_are_plain_text(tmp_path, reports):
    report = reports[0].model_copy(update={'summary': 'A & B <review> "quoted" — café'})
    output = WordRenderer(TEMPLATE).render(report, tmp_path / 'characters.docx')
    assert report.summary in [p.text for p in Document(output).paragraphs]


def test_cannot_overwrite_template_or_existing_output(tmp_path, reports):
    renderer = WordRenderer(TEMPLATE)
    before = TEMPLATE.read_bytes()
    with pytest.raises(RenderingError, match='original template'):
        renderer.render(reports[0], TEMPLATE)
    assert TEMPLATE.read_bytes() == before
    output = tmp_path / 'existing.docx'
    output.write_bytes(b'existing user document')
    with pytest.raises(RenderingError, match='already exists'):
        renderer.render(reports[0], output)
    assert output.read_bytes() == b'existing user document'


def test_template_symlink_cannot_be_overwritten(tmp_path, reports):
    link = tmp_path / 'alias.docx'
    link.symlink_to(TEMPLATE)
    with pytest.raises(RenderingError, match='original template'):
        WordRenderer(TEMPLATE).render(reports[0], link)


@pytest.mark.parametrize('content', [None, b'not a Word file'])
def test_missing_or_corrupt_template(tmp_path, reports, content, caplog):
    path = tmp_path / 'bad.docx'
    if content:
        path.write_bytes(content)
    with pytest.raises(RenderingError, match='Cannot open Word template'):
        WordRenderer(path).render(reports[0], tmp_path / 'out.docx')
    assert 'Word generation failed' in caplog.text
    assert not (tmp_path / 'out.docx').exists()


def test_missing_or_duplicate_anchor_is_rejected(tmp_path, reports):
    for label, change in [('missing', ''), ('duplicate', '[[TITLE]]')]:
        doc = Document(TEMPLATE)
        if label == 'missing':
            next(p for p in doc.paragraphs if p.text == '[[TITLE]]').text = change
        else:
            doc.add_paragraph(change)
        path = tmp_path / (label + '.docx')
        doc.save(path)
        with pytest.raises(RenderingError, match='exactly one standalone'):
            WordRenderer(path).render(reports[0], tmp_path / (label + '_out.docx'))


def test_wrong_extension_and_bad_output_parent(tmp_path, reports):
    with pytest.raises(RenderingError, match='must use .docx'):
        WordRenderer(TEMPLATE).render(reports[0], tmp_path / 'wrong.pdf')
    parent = tmp_path / 'file'
    parent.write_text('not a directory')
    with pytest.raises(RenderingError, match='Cannot write'):
        WordRenderer(TEMPLATE).render(reports[0], parent / 'out.docx')


def test_template_title_has_no_decorative_border():
    doc = Document(TEMPLATE)
    assert not doc.styles['Title'].element.xpath('./w:pPr/w:pBdr')


def test_template_creator_refuses_overwrite(tmp_path):
    from scripts.create_template import create_template
    existing = tmp_path / 'template.docx'
    existing.write_bytes(b'original')
    with pytest.raises(FileExistsError):
        create_template(existing)
    assert existing.read_bytes() == b'original'

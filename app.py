"""Streamlit UI over the same ReportService used by cli.py."""
from datetime import date
from hashlib import sha256
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError
import streamlit as st
from streamlit import config as streamlit_config

from core.exceptions import DataValidationError, ReportError
from core.input_selection import MAX_UPLOAD_BYTES, build_readers, save_uploads, save_upload
from sources.api_reader import TODOS_URL
from core.logging_config import configure_logging
from core.report_service import REPORT_LABELS, ReportService
from core.schemas import DateRange
from renderer.pdf_exporter import export_pdf, PdfExportError

# Keep the widget aligned with backend validation even when launched outside the project directory.
streamlit_config.set_option('server.maxUploadSize', MAX_UPLOAD_BYTES // (1024 * 1024))

st.set_page_config(page_title='TechInnovate Report Generator', layout='wide')
st.title('TechInnovate Report Generator')
st.caption('Create branded Word reports from Excel/CSV files, PDF files and REST API data.')
try:
    configure_logging()
except OSError:
    st.error('Cannot open the application log. Check write access to the logs folder.')
    st.stop()

settings, guidance = st.columns([2, 1], gap='large')
with settings:
    report_type = st.selectbox('Report type', options=list(REPORT_LABELS), format_func=REPORT_LABELS.get, key='report_type')
    st.subheader('Data Inputs')
    use_files = st.checkbox('Upload Files', value=True, key='use_files',
        help='Upload CSV, Excel or PDF files. Multiple files are supported when your report requires combined data.')
    uploads, sheet_name = [], None
    if use_files:
        uploads = st.file_uploader('CSV, Excel or PDF files', type=['csv', 'xlsx', 'pdf'],
            accept_multiple_files=True, key='uploads')
        st.caption('Maximum 20 MB per file. Sales reports require sales fields; KPI reports require Task ID, Task Name, User ID, Status, Created. PDF tables must have visible cell borders. Multiple task files are combined with duplicate IDs rejected. Sales reports accept at most one PDF.')
        if any(Path(file.name).suffix.lower() == '.xlsx' for file in uploads):
            sheet_name = st.text_input('Excel worksheet name (optional)', key='sheet_name',
                help='Leave blank to read the first worksheet in each workbook. A supplied name applies to all uploaded workbooks.').strip() or None
    use_api = st.checkbox('Fetch from REST API', key='use_api',
        help='Fetch data using an explicitly selected supported API schema. An internet connection is required.')
    api_kind = 'Task data'
    sales_api_url = None
    api_url = TODOS_URL
    task_mode = 'none'
    if use_api:
        if report_type == 'sales_summary':
            api_kind = st.selectbox('API data type', ['Task data', 'Sales orders'], key='api_kind')
        api_url = st.text_input('API URL', value=TODOS_URL, key='api_url')
        st.caption('Public HTTPS endpoints only (port 443); redirects are blocked. Task data requires an array with userId, id, title and completed.' if api_kind == 'Task data' else 'Public HTTPS sales endpoint only (port 443). No redirects or automatic schema inference.')
        if api_kind == 'Sales orders':
            sales_api_url = api_url
            st.info('Sales JSON: a nonempty array with order_id, order_date (YYYY-MM-DD), customer, service, revenue and currency (AUD). Documented sales aliases are supported. Replace the task endpoint with a compatible sales endpoint; /todos and shopping carts do not supply sales orders.')
        else:
            task_mode = 'live'
    left, right = st.columns(2)
    start = left.date_input('Start date', date(2026, 10, 1), key='start_date')
    end = right.date_input('End date', date(2026, 10, 31), key='end_date')

with guidance:
    st.subheader('Before you generate')
    if report_type == 'sales_summary':
        st.write('Sales Summary needs actual orders and revenue from sales CSV/Excel, a supported sales-table PDF or a Sales orders API. Task APIs supply tasks only; target-only PDFs supply benchmarks rather than orders. Combine these with sales files, or select Operations / KPI Report for API tasks alone.')
        has_sales_input = use_files and (any(Path(file.name).suffix.lower() in ('.csv', '.xlsx', '.pdf') for file in uploads))
        if not has_sales_input and sales_api_url is None:
            st.warning('No sales input selected. Add a sales CSV/Excel or sales-table PDF before generating Sales Summary.')
        st.write('Dates filter sales inclusively. Monthly targets are compared only for complete months with all targets available.')
    else:
        st.write('Upload task CSV/Excel/PDF files with Task ID, Task Name, User ID, Status and Created, or enable the Task API. Status must be Completed or Pending; Created is YYYY-MM-DD. Legacy task API dates appear as Not provided. KPIs describe all supplied tasks. Use one task source per run: uploaded files or API.')
        st.write('The date range is context only. Undated tasks cannot represent monthly activity.')
    if task_mode == 'live':
        st.info('Tasks are fetched when you generate. API failures are shown without substituting sample data.')
    st.caption('Both reports use the same company Word template.')

# Hide a previous result whenever any input changes, including file contents.
upload_signatures = tuple((file.name, sha256(file.getvalue()).hexdigest()) for file in uploads)
signature = (report_type, use_files, sheet_name, task_mode, api_url, api_kind, str(start), str(end), upload_signatures)
if st.session_state.get('result_signature') != signature:
    st.session_state.pop('generated_report', None)

if st.button('Generate Word report', type='primary', key='generate'):
    st.session_state.pop('generated_report', None)
    try:
        period = DateRange(start=start, end=end)
        with st.spinner('Reading sources and preparing your report...'):
            with TemporaryDirectory(prefix='techinnovate-report-') as temp:
                sales_files, metrics_file, task_files = [], None, []
                if use_files:
                    if not uploads:
                        raise DataValidationError('Upload at least one CSV, Excel or PDF file, or disable Upload Files to use an API alone.')
                    if report_type == 'operations_kpi':
                        task_files = [save_upload(file, temp, 'task_{}'.format(i), ('.csv', '.xlsx', '.pdf')) for i, file in enumerate(uploads)]
                    else:
                        sales_files, metrics_file = save_uploads(uploads, temp)
                if report_type == 'sales_summary' and not sales_files and metrics_file is None and sales_api_url is None:
                    raise DataValidationError('Sales Summary requires sales data containing orders and revenue. Task APIs and target-only PDFs do not supply actual sales. Enable Upload Files and add a sales CSV/Excel or supported sales-table PDF, use a Sales orders API. To report on API tasks alone, select Operations / KPI Report.')
                if report_type == 'operations_kpi' and task_mode == 'none' and not task_files:
                    raise DataValidationError('Operations / KPI Report requires a task snapshot. Upload task CSV/Excel/PDF files or enable Fetch from REST API.')
                if task_files and task_mode == 'live':
                    raise DataValidationError('Choose uploaded task files or the Task API, not both; a report uses one task snapshot.')
                filename = '{}_{}_{}.docx'.format(report_type, start, end)
                result = ReportService().generate(report_type, period,
                    build_readers(sales_files, metrics_file, task_mode, sheet_name, api_url=api_url, sales_api_url=sales_api_url, task_files=task_files), Path(temp) / filename)
                st.session_state['generated_report'] = {'data': result.path.read_bytes(), 'filename': filename,
                    'summary': result.content.summary, 'metrics': [(m.label, m.display) for m in result.content.metrics]}
                st.session_state['result_signature'] = signature
                try:
                    st.session_state['generated_report']['pdf'] = export_pdf(st.session_state['generated_report']['data'])
                except PdfExportError as exc:
                    st.session_state['generated_report']['pdf_error'] = str(exc)
    except ValidationError as exc:
        message = '; '.join(e['msg'] for e in exc.errors(include_input=False, include_url=False))
        logging.getLogger('report_generator.ui').error('Invalid inputs: %s', message)
        st.error(message)
    except (ReportError, OSError) as exc:
        logging.getLogger('report_generator.ui').error('Generation failed: %s', exc)
        st.error(str(exc))

if 'generated_report' in st.session_state:
    result = st.session_state['generated_report']
    st.success('Your Word report is ready.')
    st.write(result['summary'])
    st.table([{'Metric': name, 'Value': value} for name, value in result['metrics']])
    st.markdown("""<style>
    .st-key-report_downloads [data-testid="stHorizontalBlock"] {flex-wrap: nowrap !important;}
    .st-key-report_downloads [data-testid="column"],
    .st-key-report_downloads [data-testid="stColumn"] {min-width: 0 !important; flex: 1 1 0 !important; width: 0 !important;}
    </style>""", unsafe_allow_html=True)
    with st.container(key='report_downloads'):
        word_column, pdf_column = st.columns(2)
        word_column.download_button('Download Word report', data=result['data'], file_name=result['filename'],
                                    mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', key='download',
                                    use_container_width=True)
        pdf_column.download_button('Download PDF report', data=result.get('pdf', b''),
                                   file_name=Path(result['filename']).with_suffix('.pdf').name,
                                   mime='application/pdf', key='download_pdf', disabled='pdf' not in result,
                                   use_container_width=True)
    if 'pdf_error' in result:
        st.warning(result['pdf_error'])

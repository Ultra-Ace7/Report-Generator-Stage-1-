"""Streamlit UI over the same ReportService used by cli.py."""
from datetime import date
from hashlib import sha256
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError
import streamlit as st

from core.exceptions import DataValidationError, ReportError
from core.input_selection import SAMPLES, build_readers, save_upload
from core.logging_config import configure_logging
from core.report_service import REPORT_LABELS, ReportService
from core.schemas import DateRange

st.set_page_config(page_title='TechInnovate Report Generator', layout='wide')
st.title('TechInnovate Report Generator')
st.caption('Create branded Word reports from Excel/CSV files, PDF files and REST API data.')
try:
    configure_logging()
except OSError:
    st.error('Cannot open the application log. Check write access to the logs folder.')
    st.stop()

SOURCE_LABELS = {
    'Sales files': 'Excel / CSV',
    'PDF targets': 'PDF',
    'Task snapshot': 'API',
}

settings, guidance = st.columns([2, 1], gap='large')
with settings:
    report_type = st.selectbox('Report type', options=list(REPORT_LABELS), format_func=REPORT_LABELS.get, key='report_type')
    selected = st.multiselect('Data sources', ['Sales files', 'PDF targets', 'Task snapshot'],
                              default=['Sales files', 'PDF targets', 'Task snapshot'],
                              format_func=SOURCE_LABELS.get, key='sources')
    file_mode = st.radio('File inputs', ['Sample files', 'Upload files'], horizontal=True, key='file_mode')
    sales_uploads, metrics_upload = [], None
    if file_mode == 'Upload files':
        if 'Sales files' in selected:
            sales_uploads = st.file_uploader('Sales CSV or Excel files', type=['csv', 'xlsx'], accept_multiple_files=True, key='sales_uploads')
        if 'PDF targets' in selected:
            metrics_upload = st.file_uploader('Monthly metrics PDF', type=['pdf'], key='metrics_upload')
        st.caption('Use the documented sample column names and PDF layout. Maximum 20 MB per file.')
    sheet_name = st.text_input('Excel worksheet name', value='Sales', key='sheet_name') if 'Sales files' in selected else 'Sales'
    task_mode = 'none'
    if 'Task snapshot' in selected:
        task_mode = st.selectbox('Task data', ['offline', 'live'],
            format_func=lambda value: 'Offline demo fixture' if value == 'offline' else 'Live public demo API', key='task_mode')
    left, right = st.columns(2)
    start = left.date_input('Start date', date(2026, 10, 1), key='start_date')
    end = right.date_input('End date', date(2026, 10, 31), key='end_date')

with guidance:
    st.subheader('Before you generate')
    if report_type == 'sales_summary':
        st.write('Excel/CSV sales files are required. PDF text extraction supplies targets; REST API data or an explicit offline sample supplies a separate task overview.')
        st.write('Dates filter sales inclusively. Monthly targets are compared only for complete months with all targets available.')
    else:
        st.write('REST API task data or an explicit offline sample is required. PDF text extraction supplies an optional completion benchmark. Excel/CSV sales records do not affect task KPIs.')
        st.write('The date range is context only. Undated tasks cannot represent monthly activity.')
    if task_mode == 'offline':
        st.info('Offline demo: 5 synthetic tasks. No API request will be made.')
    elif task_mode == 'live':
        st.info('Live demo: tasks are fetched when you generate. API failures are shown; offline data is never substituted automatically.')
    st.caption('All supplied sample files contain fictional data. Both reports use the same company Word template.')

# Hide a previous result whenever any input changes, including file contents.
upload_signatures = tuple((file.name, sha256(file.getvalue()).hexdigest()) for file in sales_uploads)
pdf_signature = (metrics_upload.name, sha256(metrics_upload.getvalue()).hexdigest()) if metrics_upload is not None else None
signature = (report_type, tuple(selected), file_mode, sheet_name, task_mode, str(start), str(end), upload_signatures, pdf_signature)
if st.session_state.get('result_signature') != signature:
    st.session_state.pop('generated_report', None)

if st.button('Generate Word report', type='primary', key='generate'):
    st.session_state.pop('generated_report', None)
    try:
        period = DateRange(start=start, end=end)
        with st.spinner('Reading sources and preparing your report...'):
            with TemporaryDirectory(prefix='techinnovate-report-') as temp:
                sales_files, metrics_file = [], None
                if 'Sales files' in selected:
                    if file_mode == 'Sample files':
                        sales_files = [SAMPLES / 'sales.csv']
                    else:
                        if not sales_uploads:
                            raise DataValidationError('Upload at least one sales CSV or Excel file, or choose Sample files.')
                        sales_files = [save_upload(file, temp, 'sales_{}'.format(i), ('.csv', '.xlsx')) for i, file in enumerate(sales_uploads)]
                if 'PDF targets' in selected:
                    if file_mode == 'Sample files':
                        metrics_file = SAMPLES / 'monthly_metrics.pdf'
                    else:
                        if metrics_upload is None:
                            raise DataValidationError('Upload a monthly metrics PDF, or deselect PDF.')
                        metrics_file = save_upload(metrics_upload, temp, 'metrics', ('.pdf',))
                filename = '{}_{}_{}_{}.docx'.format(report_type, start, end, task_mode)
                result = ReportService().generate(report_type, period,
                    build_readers(sales_files, metrics_file, task_mode, sheet_name), Path(temp) / filename)
                st.session_state['generated_report'] = {'data': result.path.read_bytes(), 'filename': filename,
                    'summary': result.content.summary, 'metrics': [(m.label, m.display) for m in result.content.metrics]}
                st.session_state['result_signature'] = signature
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
    st.download_button('Download Word report', data=result['data'], file_name=result['filename'],
                       mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', key='download')

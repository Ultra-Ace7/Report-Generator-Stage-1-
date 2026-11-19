"""Idempotent file logging for CLI calls and Streamlit reruns."""
import logging
from pathlib import Path
from threading import Lock

_LOCK = Lock()
DEFAULT_LOG = Path(__file__).resolve().parents[1] / 'logs' / 'report_generator.log'


def configure_logging(path=DEFAULT_LOG):
    path = Path(path).resolve()
    with _LOCK:
        logger = logging.getLogger('report_generator')
        logger.setLevel(logging.INFO)
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler) and handler.baseFilename == str(path):
                return
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
        logger.addHandler(handler)

"""Verify that the Python 3.9 dependency stack can load together."""
import importlib

import pytest


@pytest.mark.parametrize("module", [
    "streamlit", "pandas", "openpyxl", "pdfplumber", "httpx",
    "docxtpl", "docx", "matplotlib", "pydantic",
])
def test_dependency_import(module):
    importlib.import_module(module)

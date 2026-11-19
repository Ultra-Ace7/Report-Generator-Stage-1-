"""Reproducible offline HTTP mock; production URL restrictions are unchanged."""
import json
from unittest.mock import patch
import httpx
from cli import main
from core.input_selection import SAMPLES


def run():
    from sources.csv_excel import CsvExcelReader
    payload = [order.model_dump(mode='json') for order in CsvExcelReader(SAMPLES / 'Sales_Summary_Dummy_Data/sales_2026-10.csv').read().orders]
    transport = lambda: httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    with patch('sources.api_reader.PublicHTTPTransport', transport):
        return main()


if __name__ == '__main__':
    raise SystemExit(run())

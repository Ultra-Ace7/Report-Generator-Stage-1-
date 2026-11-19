import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from core.exceptions import ReportError
from sources.api_reader import ApiTaskReader, OfflineTaskReader, TODOS_URL
from sources.base import merge_sources
from sources.csv_excel import CsvExcelReader
from sources.pdf_reader import PdfMetricsReader

SAMPLES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
TASK = {"userId": 1, "id": 1, "title": "Demo", "completed": True}


def test_live_adapter_uses_timeout_and_preserves_caller_client():
    def handler(request):
        assert str(request.url) == TODOS_URL
        assert request.extensions["timeout"]["read"] == 3
        return httpx.Response(200, json=[TASK])
    before = datetime.now(timezone.utc)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        snapshot = ApiTaskReader(client, timeout=3).read().snapshot
        assert not client.is_closed
    assert snapshot.mode == "live_demo"
    assert before <= snapshot.captured_at <= datetime.now(timezone.utc)
    assert snapshot.source == TODOS_URL
    assert snapshot.tasks[0].completed is True


@pytest.mark.parametrize("code", [301, 404, 429, 500])
def test_http_failures(code, caplog):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(code))) as client:
        with pytest.raises(ReportError, match="HTTP {}".format(code)):
            ApiTaskReader(client).read()
    assert "HTTP {}".format(code) in caplog.text


@pytest.mark.parametrize("error,message", [(httpx.ReadTimeout, "timed out"), (httpx.ConnectError, "Cannot connect")])
def test_network_failure_never_falls_back_to_fixtures(error, message):
    def handler(request):
        raise error("simulated", request=request)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ReportError, match=message):
            ApiTaskReader(client).read()


@pytest.mark.parametrize("payload", [[], {}, [None], [dict(TASK, completed="false")], [TASK, TASK], [{"id": 1}], [dict(TASK, extra="unexpected")]])
def test_invalid_api_payload(payload):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as client:
        with pytest.raises(ReportError):
            ApiTaskReader(client).read()


def test_invalid_json():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text="<html>bad</html>"))) as client:
        with pytest.raises(ReportError, match="invalid JSON"):
            ApiTaskReader(client).read()


def test_offline_metadata_cannot_claim_live_data(tmp_path):
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps(dict(captured_at="2026-11-17T09:00:00+11:00", source="Demo", mode="live_demo")))
    with pytest.raises(ReportError, match="labelled offline_fixture"):
        OfflineTaskReader(SAMPLES / "todos_fixture.json", meta).read()


def test_all_three_sources_merge_and_keep_snapshot_distinct():
    sales = CsvExcelReader(SAMPLES / "sales.csv").read()
    metrics = PdfMetricsReader(SAMPLES / "monthly_metrics.pdf").read()
    api = OfflineTaskReader(SAMPLES / "todos_fixture.json", SAMPLES / "todos_fixture_metadata.json").read()
    combined = merge_sources(sales, metrics, api)
    assert len(combined.orders) == 8
    assert len(combined.monthly_targets) == 2
    assert len(combined.snapshot.tasks) == 5
    assert combined.snapshot.mode == "offline_fixture"
    assert combined.benchmark.completion_rate_target == Decimal("0.8")
    with pytest.raises(ReportError, match="only one task snapshot"):
        merge_sources(api, api)

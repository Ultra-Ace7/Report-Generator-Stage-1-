"""JSONPlaceholder task adapter with explicit live and offline modes."""
import json
import math
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path

import httpx

from core.exceptions import DataValidationError, SourceReadError
from core.schemas import Task, TaskSnapshot
from sources.base import SourceData, read_boundary
from sources.public_http import PublicHTTPTransport, validate_api_url

TODOS_URL = "https://jsonplaceholder.typicode.com/todos"


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DataValidationError("API JSON contains duplicate key '{}'.".format(key))
        result[key] = value
    return result


def normalize_tasks(payload):
    if not isinstance(payload, list) or not payload:
        raise DataValidationError("Task API must return a nonempty JSON array.")
    if isinstance(payload[0], dict) and any(key in payload[0] for key in ('Task ID', 'Task Name', 'Created')):
        from sources.task_files import task_rows
        tasks = []
        for record in payload:
            if not isinstance(record, dict):
                raise DataValidationError('Task API records must be objects.')
            tasks.extend(task_rows([list(record), list(record.values())]))
        return tasks
    tasks = []
    for number, record in enumerate(payload, 1):
        if not isinstance(record, dict) or set(record) != {"userId", "id", "title", "completed"}:
            raise DataValidationError("Task record {} must contain userId, id, title and completed only.".format(number))
        with read_boundary("Task record {}".format(number)):
            tasks.append(Task(task_id=record["id"], user_id=record["userId"], title=record["title"], completed=record["completed"]))
    return tasks


class ApiTaskReader:
    api_label = "Task"
    def __init__(self, client=None, timeout=10.0, url=TODOS_URL):
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("API timeout must be a positive finite number of seconds.")
        self.url = validate_api_url(url)
        self.client = client
        self.timeout = timeout

    def fetch_payload(self):
        with read_boundary(self.api_label + " REST API"):
            try:
                if self.client is None:
                    with httpx.Client(transport=PublicHTTPTransport(), trust_env=False) as client:
                        return self._fetch(client)
                else:
                    return self._fetch(self.client)
            except httpx.TimeoutException as exc:
                raise SourceReadError(self.api_label + " API timed out. Please try again.") from exc
            except httpx.HTTPStatusError as exc:
                raise SourceReadError("{} API returned HTTP {}.".format(self.api_label, exc.response.status_code)) from exc
            except httpx.RequestError as exc:
                raise SourceReadError("Cannot connect to {} API. Check your network and try again.".format(self.api_label.lower())) from exc

    def _fetch(self, client):
        with client.stream('GET', self.url, timeout=self.timeout, follow_redirects=False) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > 20 * 1024 * 1024:
                    raise DataValidationError('API response exceeds the 20 MB limit.')
                chunks.append(chunk)
            try:
                return json.loads(b''.join(chunks), parse_float=Decimal,
                                  object_pairs_hook=unique_json_object)
            except (ValueError, UnicodeError) as exc:
                raise DataValidationError(self.api_label + ' API returned invalid JSON.') from exc

    def read(self) -> SourceData:
        with read_boundary(self.api_label + " REST API"):
            payload = self.fetch_payload()
            return SourceData(snapshot=TaskSnapshot(
                tasks=normalize_tasks(payload), captured_at=datetime.now(timezone.utc),
                source=self.url, mode="live_demo",
            ))


class OfflineTaskReader:
    """Explicit local fixture mode; never an automatic fallback for API failure."""
    def __init__(self, path, metadata_path):
        self.path = Path(path)
        self.metadata_path = Path(metadata_path)

    def read(self) -> SourceData:
        with read_boundary("Offline task fixture"):
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            except ValueError as exc:
                raise DataValidationError("Offline task fixture or metadata contains invalid JSON.") from exc
            if not isinstance(metadata, dict) or set(metadata) != {"captured_at", "source", "mode"}:
                raise DataValidationError("Offline metadata must contain captured_at, source and mode only.")
            if metadata["mode"] != "offline_fixture":
                raise DataValidationError("Offline data must be labelled offline_fixture.")
            return SourceData(snapshot=TaskSnapshot(tasks=normalize_tasks(payload), **metadata))

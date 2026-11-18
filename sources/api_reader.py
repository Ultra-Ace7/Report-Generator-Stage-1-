"""JSONPlaceholder task adapter with explicit live and offline modes."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import httpx

from core.exceptions import DataValidationError, SourceReadError
from core.schemas import Task, TaskSnapshot
from sources.base import SourceData, read_boundary

TODOS_URL = "https://jsonplaceholder.typicode.com/todos"


def normalize_tasks(payload):
    if not isinstance(payload, list) or not payload:
        raise DataValidationError("Task API must return a nonempty JSON array.")
    tasks = []
    for number, record in enumerate(payload, 1):
        if not isinstance(record, dict) or set(record) != {"userId", "id", "title", "completed"}:
            raise DataValidationError("Task record {} must contain userId, id, title and completed only.".format(number))
        with read_boundary("Task record {}".format(number)):
            tasks.append(Task(task_id=record["id"], user_id=record["userId"], title=record["title"], completed=record["completed"]))
    return tasks


class ApiTaskReader:
    def __init__(self, client=None, timeout=10.0):
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("API timeout must be a positive finite number of seconds.")
        self.client = client
        self.timeout = timeout

    def read(self) -> SourceData:
        with read_boundary("JSONPlaceholder task API"):
            try:
                if self.client is None:
                    with httpx.Client() as client:
                        response = client.get(TODOS_URL, timeout=self.timeout, follow_redirects=False)
                else:
                    response = self.client.get(TODOS_URL, timeout=self.timeout, follow_redirects=False)
                response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise SourceReadError("Task API timed out. Please try again or explicitly select offline demo data.") from exc
            except httpx.HTTPStatusError as exc:
                raise SourceReadError("Task API returned HTTP {}.".format(exc.response.status_code)) from exc
            except httpx.RequestError as exc:
                raise SourceReadError("Cannot connect to task API. Check your network and try again.") from exc
            try:
                payload = response.json()
            except (ValueError, UnicodeError) as exc:
                raise DataValidationError("Task API returned invalid JSON.") from exc
            return SourceData(snapshot=TaskSnapshot(
                tasks=normalize_tasks(payload), captured_at=datetime.now(timezone.utc),
                source=TODOS_URL, mode="live_demo",
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

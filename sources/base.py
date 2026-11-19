"""Shared reader contract, validation boundary and normalized results."""
import logging
from contextlib import contextmanager
from typing import Protocol

from pydantic import ValidationError

from core.exceptions import DataValidationError, SourceReadError
from core.schemas import SourceData

logger = logging.getLogger("report_generator.sources")


class DataReader(Protocol):
    def read(self) -> SourceData:
        """Read and validate input without depending on any report type."""
        ...


@contextmanager
def read_boundary(label):
    """Give callers predictable errors and log failures without raw records."""
    try:
        yield
    except ValidationError as exc:
        errors = exc.errors(include_url=False, include_input=False)
        detail = "; ".join("{}: {}".format(".".join(map(str, e["loc"])) or "data", e["msg"]) for e in errors[:3])
        message = "{}: invalid data. {}".format(label, detail)
        logger.error(message)
        raise DataValidationError(message) from exc
    except (DataValidationError, SourceReadError) as exc:
        logger.error("%s: %s", label, exc)
        raise
    except (OSError, UnicodeError) as exc:
        message = "{}: cannot read input; check the file exists, permissions and encoding.".format(label)
        logger.error(message)
        raise SourceReadError(message) from exc
    else:
        logger.info("%s: input loaded successfully", label)


def merge_sources(*items: SourceData) -> SourceData:
    """Validate duplicate business keys after combining multiple inputs."""
    with read_boundary("Combined sources"):
        snapshots = [item.snapshot for item in items if item.snapshot is not None]
        benchmarks = [item.benchmark for item in items if item.benchmark is not None]
        if len(snapshots) > 1 or len(benchmarks) > 1:
            raise DataValidationError("Select only one task snapshot and one snapshot benchmark.")
        return SourceData(
            orders=tuple(order for item in items for order in item.orders),
            monthly_targets=tuple(target for item in items for target in item.monthly_targets),
            snapshot=snapshots[0] if snapshots else None,
            benchmark=benchmarks[0] if benchmarks else None,
        )

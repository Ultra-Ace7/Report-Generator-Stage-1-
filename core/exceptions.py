"""Errors that UI and CLI boundaries will display and log."""


class ReportError(Exception):
    """Base class for expected report-generation failures."""


class DataValidationError(ReportError):
    """Input data cannot support the requested operation."""


class SourceReadError(ReportError):
    """An input file or remote source could not be read."""

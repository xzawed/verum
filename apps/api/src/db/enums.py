"""Type-safe string enumerations for database status columns.

All values match the CHECK constraints in Alembic migrations so that
Python-side logic and SQL are consistent without a second source of truth.
"""
from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    """verum_jobs.status — lifecycle of a background job."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class AnalysisStatus(StrEnum):
    """analyses / inferences / generations .status columns."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class HarvestSourceStatus(StrEnum):
    """harvest_sources.status — lifecycle of a crawl source."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    CRAWLING = "crawling"
    DONE = "done"
    ERROR = "error"

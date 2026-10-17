"""Where a heavy report's response comes from (37d)."""
from __future__ import annotations

from enum import StrEnum


class ReportSource(StrEnum):
    SNAPSHOT = "snapshot"
    LIVE = "live"
    UNAVAILABLE = "unavailable"


def report_source(has_snapshot: bool, production: bool) -> ReportSource:
    """A stored snapshot wins; production never computes one live.

    A live replay of the NFL line grading peaked at 647 MB, past the hosted
    demo's 512 MB, so production answers 503 until the weekly job has run.
    """
    if has_snapshot:
        return ReportSource.SNAPSHOT
    return ReportSource.UNAVAILABLE if production else ReportSource.LIVE

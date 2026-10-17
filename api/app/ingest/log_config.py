"""
ingest/log_config.py

Shared logging setup for the ingest entry points.

httpx and urllib3 log the full request URL, and several providers take their
credential as a query-string parameter rather than a header (odds-api.io uses
`?apiKey=`), so their INFO/DEBUG records write live API keys into the log file.
Capping those loggers at WARNING keeps request URLs out of the output while
leaving each script's own logger at whatever level it asked for.
"""
from __future__ import annotations

import logging

# Loggers that emit full request URLs, query string included.
_URL_EMITTING_LOGGERS = ("httpx", "httpcore", "urllib3", "requests.packages.urllib3")


def configure_ingest_logging(
    level: int = logging.INFO,
    fmt: str = "%(levelname)s:%(name)s:%(message)s",
) -> None:
    """Configure root logging for an ingest script and silence URL-leaking loggers."""
    logging.basicConfig(level=level, format=fmt)
    for name in _URL_EMITTING_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

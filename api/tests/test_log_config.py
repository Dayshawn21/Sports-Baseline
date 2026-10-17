import logging

import pytest

from app.ingest.log_config import _URL_EMITTING_LOGGERS, configure_ingest_logging


@pytest.fixture(autouse=True)
def restore_logger_levels():
    saved = {name: logging.getLogger(name).level for name in _URL_EMITTING_LOGGERS}
    yield
    for name, level in saved.items():
        logging.getLogger(name).setLevel(level)


def test_url_emitting_loggers_are_capped_at_warning():
    for name in _URL_EMITTING_LOGGERS:
        logging.getLogger(name).setLevel(logging.DEBUG)

    configure_ingest_logging()

    for name in _URL_EMITTING_LOGGERS:
        assert logging.getLogger(name).level == logging.WARNING


def test_request_url_carrying_an_api_key_is_not_emitted(caplog):
    configure_ingest_logging()

    with caplog.at_level(logging.DEBUG):
        logging.getLogger("httpx").info(
            'HTTP Request: GET %s "HTTP/1.1 200 OK"',
            "https://api.odds-api.io/v3/events?sport=tennis&apiKey=SECRET123",
        )

    assert "SECRET123" not in caplog.text


def test_debug_level_scripts_still_silence_url_loggers():
    """player_stats runs at DEBUG, which is what surfaced urllib3 request lines."""
    configure_ingest_logging(level=logging.DEBUG)

    assert logging.getLogger("urllib3").level == logging.WARNING

import pytest
from tenacity import wait_none

from app import rate_limit
from app.ingest import nflverse
from app.services.ask import guardrails


@pytest.fixture(autouse=True)
def _no_nflverse_retry_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    # NFLverse 404 paths retry with real waits (about 70 s); tests keep the attempts, not the sleep.
    monkeypatch.setattr(nflverse, "RELEASE_RETRY_WAIT", wait_none())


@pytest.fixture(autouse=True)
def _fresh_rate_limits() -> None:
    # The counters are process-wide; every test starts with an empty window.
    rate_limit.storage.reset()


@pytest.fixture(autouse=True)
def _fresh_ask_spend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guardrails, "spend", guardrails.DailySpend())

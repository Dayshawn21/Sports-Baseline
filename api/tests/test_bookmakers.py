import asyncio

import pytest

from app.core.bookmakers import MAX_BOOKMAKER_COUNT, bookmaker_scope_param, normalize_bookmaker_scope, stored_book_keys
from app.ingest import odds_api


def test_normalize_bookmaker_scope_trims_and_deduplicates_case_insensitively() -> None:
    assert normalize_bookmaker_scope(" DraftKings,bet365,draftkings, Bet365 ") == (
        "DraftKings", "bet365",
    )


def test_bookmaker_scope_param_preserves_the_normalized_order() -> None:
    assert bookmaker_scope_param("Bet365,DraftKings") == "Bet365,DraftKings"


@pytest.mark.parametrize("scope", ["", ", ,"])
def test_normalize_bookmaker_scope_rejects_an_empty_scope(scope: str) -> None:
    with pytest.raises(ValueError, match="At least one bookmaker"):
        normalize_bookmaker_scope(scope)


def test_normalize_bookmaker_scope_rejects_more_than_thirty_unique_books() -> None:
    scope = ",".join(f"Book{index}" for index in range(MAX_BOOKMAKER_COUNT + 1))

    with pytest.raises(ValueError, match="At most 30 bookmakers"):
        normalize_bookmaker_scope(scope)


def test_invalid_capture_scope_fails_before_any_network_call(tmp_path) -> None:
    with pytest.raises(ValueError, match="At least one bookmaker"):
        asyncio.run(odds_api.capture_market_inventory(tmp_path / "inventory.md", bookmakers="", api_key="test-key"))


def test_stored_book_keys_match_how_the_ingest_names_books() -> None:
    assert stored_book_keys("DraftKings, FanDuel,draftkings") == ["draftkings", "fanduel"]

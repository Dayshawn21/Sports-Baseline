from app.ingest.api_sports_nfl import FINAL_STATUSES, NFL_LEAGUE_ID


def test_api_sports_nfl_ingest_only_uses_documented_final_statuses() -> None:
    assert FINAL_STATUSES == {"FT", "AOT"}
    assert NFL_LEAGUE_ID == 1

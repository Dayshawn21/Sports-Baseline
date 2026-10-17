from datetime import UTC, date, datetime

from app.ingest.nfl_odds_io import batches, can_request, select_events

NOW = datetime(2026, 10, 7, 15, tzinfo=UTC)
GAMES = [
    {"game_id": 65, "game_date": date(2026, 10, 8), "start_utc": datetime(2026, 10, 9, 0, 15, tzinfo=UTC), "home_team": "DAL", "away_team": "TB"},
    {"game_id": 66, "game_date": date(2026, 10, 7), "start_utc": datetime(2026, 10, 7, 13, 30, tzinfo=UTC), "home_team": "JAX", "away_team": "PHI"},
]


def _event(event_id: int, home: str, away: str, day: str, status: str = "pending", league: str = "usa-nfl") -> dict[str, object]:
    return {"id": event_id, "home": home, "away": away, "date": f"{day}T00:15:00Z", "status": status, "league": {"slug": league}}


def test_a_slate_splits_into_requests_of_at_most_ten_games() -> None:
    assert [len(batch) for batch in batches(list(range(15)))] == [10, 5]
    assert batches([]) == []


def test_the_floor_stops_before_a_request_would_cross_it_and_on_an_unknown_balance() -> None:
    assert can_request(21, 20)
    assert not can_request(20, 20)
    assert not can_request(None, 20)


def test_only_pending_nfl_events_for_unstarted_stored_games_are_selected() -> None:
    events = [
        _event(1, "Dallas Cowboys", "Tampa Bay Buccaneers", "2026-10-09"),
        _event(2, "Tampa Bay Buccaneers", "Dallas Cowboys", "2026-10-09"),
        _event(3, "Jacksonville Jaguars", "Philadelphia Eagles", "2026-10-07"),
        _event(4, "Dallas Cowboys", "Tampa Bay Buccaneers", "2026-10-09", status="settled"),
        _event(5, "Miami Dolphins", "Buffalo Bills", "2026-10-09"),
        _event(6, "Dallas Cowboys", "Tampa Bay Buccaneers", "2026-10-09", league="ncaa"),
    ]

    selected, skipped = select_events(events, GAMES, NOW)

    assert selected == {1: (65, True), 2: (65, False)}
    assert dict(skipped) == {"started": 1, "not_pending": 1, "unmatched": 1}

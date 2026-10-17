"""The slate and the match page must predict through one path (32a)."""
import asyncio
from datetime import date, datetime, timezone

from app.repositories import matches as match_repo
from app.repositories.matches import Match, MatchMeta, get_match
from app.services.tennis import predictor


def _match(match_id: int, match_date: date) -> Match:
    return Match(
        id=match_id, match_key=f"k{match_id}", match_date=match_date,
        start_utc=None, tour="ATP", surface="Hard", tournament="Tokyo", round="R16",
        best_of=3, p1_id=1, p2_id=2, p1_rank=19, p2_rank=7, winner_id=None,
        status="scheduled", sofascore_id=None, livetennis_id=None,
    )


def _patch(monkeypatch, upcoming: list[Match]) -> list[tuple]:
    calls: list[tuple] = []

    async def fake_upcoming(_db, _match_date):
        return upcoming

    async def fake_predict_matches(_db, _registry, matches, ref_date):
        calls.append((matches, ref_date))
        return ["prediction"]

    monkeypatch.setattr(match_repo, "get_upcoming", fake_upcoming)
    monkeypatch.setattr(predictor, "predict_matches", fake_predict_matches)
    return calls


def test_predict_today_hands_its_matches_to_the_shared_path(monkeypatch):
    upcoming = [_match(1, date(2026, 9, 28)), _match(2, date(2026, 9, 29))]
    calls = _patch(monkeypatch, upcoming)

    result = asyncio.run(predictor.predict_today(None, None, [date(2026, 9, 29), date(2026, 9, 28)]))

    assert result == ["prediction"]
    assert calls == [(upcoming, date(2026, 9, 28))]


def test_a_single_date_is_its_own_reference_date(monkeypatch):
    calls = _patch(monkeypatch, [_match(1, date(2026, 9, 28))])

    asyncio.run(predictor.predict_today(None, None, date(2026, 9, 28)))

    assert calls[0][1] == date(2026, 9, 28)


def test_no_upcoming_matches_skips_the_batch(monkeypatch):
    calls = _patch(monkeypatch, [])

    assert asyncio.run(predictor.predict_today(None, None, date(2026, 9, 28))) == []
    assert calls == []


def test_predict_matches_with_no_matches_returns_empty():
    assert asyncio.run(predictor.predict_matches(None, None, [], date(2026, 9, 28))) == []


class _Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _Db:
    def __init__(self, row):
        self.row = row

    async def execute(self, *_args, **_kwargs):
        return _Result(self.row)


def test_get_match_splits_the_row_into_match_and_meta():
    start = datetime(2026, 9, 28, 10, 30, tzinfo=timezone.utc)
    row = (
        5, "k5", date(2026, 9, 28), start, "ATP", "Hard", "Tokyo", "R16", 3,
        1, 2, 19, 7, 1, "completed", None, 77, True, "7-6 6-4",
    )

    found = asyncio.run(get_match(_Db(row), 5))

    assert found is not None
    match, meta = found
    assert match.id == 5 and match.winner_id == 1 and match.livetennis_id == 77
    assert match.status == "completed"
    assert meta == MatchMeta(indoor=True, score="7-6 6-4")


def test_get_match_unknown_id_is_none():
    assert asyncio.run(get_match(_Db(None), 404)) is None

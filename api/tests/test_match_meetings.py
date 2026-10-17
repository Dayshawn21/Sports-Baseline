import asyncio
from datetime import date

from app.repositories.matches import MatchMeeting, get_meetings, orient_meeting

LEHECKA, BERGS = 16, 45


def test_a_meeting_stored_the_same_way_round_keeps_its_score():
    assert orient_meeting(LEHECKA, LEHECKA, "6-2 6-1", LEHECKA, BERGS) == ("p1", "6-2 6-1")


def test_a_meeting_stored_the_other_way_round_still_reads_from_the_winner():
    # Stored with Bergs as p1 and Lehecka winning, so the stored score is Bergs-first.
    assert orient_meeting(BERGS, LEHECKA, "2-6 1-6", LEHECKA, BERGS) == ("p1", "6-2 6-1")


def test_the_viewed_p2_winning_is_p2():
    assert orient_meeting(LEHECKA, BERGS, "4-6 6-7", LEHECKA, BERGS) == ("p2", "6-4 7-6")


def test_without_a_winner_the_score_reads_from_the_viewed_p1():
    assert orient_meeting(BERGS, None, "3-6 2-1", LEHECKA, BERGS) == (None, "6-3 1-2")
    assert orient_meeting(LEHECKA, None, None, LEHECKA, BERGS) == (None, None)


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class _Db:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.params = None

    async def execute(self, sql, params):
        self.sql = str(sql)
        self.params = params
        return _Result(self.rows)


def test_meetings_are_capped_before_the_viewed_match_and_newest_first():
    db = _Db([])

    asyncio.run(get_meetings(db, LEHECKA, BERGS, date(2026, 9, 30)))

    assert db.params == {"a": LEHECKA, "b": BERGS, "before": date(2026, 9, 30)}
    assert "match_date < :before" in db.sql
    assert "status = 'completed'" in db.sql
    assert "ORDER BY match_date DESC" in db.sql


def test_meeting_rows_are_oriented_to_the_viewed_match():
    db = _Db([
        (date(2026, 2, 18), "Doha", "R16", "Hard", "2-6 1-6", LEHECKA, BERGS),
        (date(2025, 5, 2), "Madrid", "R64", "Clay", "7-5 6-4", BERGS, BERGS),
    ])

    meetings = asyncio.run(get_meetings(db, LEHECKA, BERGS, date(2026, 9, 30)))

    assert meetings == [
        MatchMeeting(date(2026, 2, 18), "Doha", "R16", "Hard", "6-2 6-1", "p1"),
        MatchMeeting(date(2025, 5, 2), "Madrid", "R64", "Clay", "7-5 6-4", "p2"),
    ]

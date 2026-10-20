import asyncio
from datetime import date

from app.core.box_score_join import BoxScoreCandidate, JoinResult
from app.repositories import matches
from app.repositories.matches import get_match_players, get_recent_completed_matches


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class _Db:
    def __init__(self, results):
        self.results = iter(results)

    async def execute(self, *_args, **_kwargs):
        return _Result(next(self.results))


def test_match_players_returns_both_players_in_match_order():
    db = _Db([[(date(2026, 9, 22), 11, "Alycia Parks", 22, "Mei Yamaguchi")]])

    match = asyncio.run(get_match_players(db, 99))

    assert match is not None
    match_date, players = match
    assert match_date == date(2026, 9, 22)
    assert [(player.id, player.name) for player in players] == [
        (11, "Alycia Parks"),
        (22, "Mei Yamaguchi"),
    ]


RECENT = [
    (11, date(2026, 9, 20), "Opponent One", "6-4 6-4", "W", False, 101),
    (11, date(2026, 9, 18), "Opponent Two", "3-6 6-4 3-6", "L", False, 102),
    (22, date(2026, 9, 19), "Opponent Three", "6-2 6-3", "L", True, 103),
]
BOX = BoxScoreCandidate(
    stats_id=1, match_date=date(2026, 9, 14), result="W", opponent_name="Opponent One",
    score="6-4 6-4", aces=8, double_faults=2, break_points_converted=4, break_chances_created=5,
)


class _Context:
    def __init__(self, joined: JoinResult) -> None:
        self.joined = joined

    def join(self) -> JoinResult:
        return self.joined


def _recent_form(monkeypatch, joins: dict) -> tuple[dict, list]:
    asked: list = []

    async def candidates(_db, pairs, *, sources):
        assert sources == ("tennisabstract", "tennismylife")
        asked.extend(pairs)
        return {pair: _Context(joined) for pair, joined in joins.items()}

    monkeypatch.setattr(matches, "get_box_score_candidates", candidates)
    form = asyncio.run(get_recent_completed_matches(_Db([RECENT]), [11, 22], date(2026, 9, 22)))
    return form, asked


def test_recent_form_keeps_each_player_oriented_and_newest_first(monkeypatch):
    form, _ = _recent_form(monkeypatch, {})

    assert [(item.opponent_name, item.result) for item in form[11]] == [
        ("Opponent One", "W"),
        ("Opponent Two", "L"),
    ]
    assert [(item.opponent_name, item.result) for item in form[22]] == [
        ("Opponent Three", "L"),
    ]
    assert form[11][1].score == "3-6 6-4 3-6"
    assert form[22][0].score == "2-6 3-6"


def test_box_scores_are_looked_up_for_every_recent_match(monkeypatch):
    _, asked = _recent_form(monkeypatch, {})
    assert asked == [(11, 101), (11, 102), (22, 103)]


def test_a_joined_match_shows_its_box_score(monkeypatch):
    form, _ = _recent_form(monkeypatch, {(11, 101): JoinResult(BOX, "joined")})
    first = form[11][0]
    assert (first.aces, first.double_faults, first.break_chances_created, first.break_points_converted) == (8, 2, 5, 4)


def test_an_unjoined_match_stays_blank(monkeypatch):
    form, _ = _recent_form(monkeypatch, {(11, 102): JoinResult(None, "ambiguous")})
    second = form[11][1]
    assert (second.aces, second.double_faults, second.break_chances_created, second.break_points_converted) == (
        None, None, None, None,
    )
    assert form[22][0].aces is None  # no candidates loaded at all

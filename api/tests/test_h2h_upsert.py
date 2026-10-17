"""
Migration 0013 stores every h2h row with the lower player id first, enforced by
a CHECK constraint, so one pairing cannot exist under two orientations and drift
apart. Callers pass match order, which is arbitrary, so `upsert_h2h` normalizes
before writing.
"""
import asyncio

from app.repositories.matches import upsert_h2h

ALICE, BOB = 1, 2


class _RecordingSession:
    def __init__(self):
        self.params = None

    async def execute(self, _stmt, params):
        self.params = params
        return None


def _upsert(p1_id, p2_id, p1_wins, p2_wins, surface=None):
    db = _RecordingSession()
    asyncio.run(upsert_h2h(db, p1_id, p2_id, p1_wins, p2_wins, surface=surface))
    return db.params


def test_reversed_pair_is_swapped_and_wins_follow():
    params = _upsert(BOB, ALICE, 3, 1)

    assert (params["p1"], params["p2"]) == (ALICE, BOB)
    assert (params["w1"], params["w2"]) == (1, 3)


def test_canonical_pair_is_written_unchanged():
    params = _upsert(ALICE, BOB, 3, 1)

    assert (params["p1"], params["p2"]) == (ALICE, BOB)
    assert (params["w1"], params["w2"]) == (3, 1)


def test_surface_is_preserved_when_swapping():
    params = _upsert(BOB, ALICE, 2, 0, surface="Clay")

    assert params["surf"] == "Clay"
    assert (params["p1"], params["p2"]) == (ALICE, BOB)
    assert (params["w1"], params["w2"]) == (0, 2)


def test_written_row_always_satisfies_the_check_constraint():
    for a, b in [(ALICE, BOB), (BOB, ALICE)]:
        params = _upsert(a, b, 1, 0)

        assert params["p1"] < params["p2"]

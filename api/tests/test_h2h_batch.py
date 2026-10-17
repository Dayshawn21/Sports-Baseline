"""
`h2h` rows are stored in whichever order the two players first met, which need
not match the `p1`/`p2` order of the match being predicted. The batch fetch used
to filter with `p1_id = ANY(:p1ids) AND p2_id = ANY(:p2ids)`, so a reversed row
was never returned and its wins were never flipped.

The fake session below applies the same filter the SQL does, so these exercise
the real orientation behavior rather than asserting that the mapping code the
bug never reached is correct.
"""
import asyncio

from app.repositories.matches import get_h2h_batch

ALICE, BOB, CARA, DAN = 1, 2, 3, 4


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeSession:
    """Applies `WHERE p1_id = ANY(:ids) AND p2_id = ANY(:ids)` over a fixture table."""

    def __init__(self, table):
        self.table = table

    async def execute(self, _stmt, params):
        ids = set(params["ids"])
        return _FakeResult([r for r in self.table if r[0] in ids and r[1] in ids])


def _batch(table, pairs):
    return asyncio.run(get_h2h_batch(_FakeSession(table), pairs))


def test_reversed_row_is_found_and_wins_are_flipped():
    # Stored as (BOB, ALICE) 3-1, but the match is ALICE vs BOB.
    result = _batch([(BOB, ALICE, None, 3, 1)], [(ALICE, BOB, None)])

    assert result[(ALICE, BOB, None)] == {"p1_wins": 1, "p2_wins": 3}


def test_same_direction_row_is_not_flipped():
    result = _batch([(ALICE, BOB, None, 3, 1)], [(ALICE, BOB, None)])

    assert result[(ALICE, BOB, None)] == {"p1_wins": 3, "p2_wins": 1}


def test_surface_rows_are_keyed_separately():
    table = [
        (BOB, ALICE, None, 3, 1),
        (BOB, ALICE, "Clay", 2, 0),
    ]

    result = _batch(table, [(ALICE, BOB, None), (ALICE, BOB, "Clay")])

    assert result[(ALICE, BOB, None)] == {"p1_wins": 1, "p2_wins": 3}
    assert result[(ALICE, BOB, "Clay")] == {"p1_wins": 0, "p2_wins": 2}


def test_unrelated_pair_sharing_the_slate_is_not_returned():
    """Both players are on the slate but are not playing each other."""
    result = _batch([(ALICE, CARA, None, 5, 5)], [(ALICE, BOB, None), (CARA, DAN, None)])

    assert result == {}


def test_no_pairs_short_circuits():
    assert _batch([], []) == {}

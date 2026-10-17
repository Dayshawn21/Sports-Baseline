"""The upserts must never let an absent field overwrite a stored one.

Coverage for the livetennisapi profile fields runs 90-100%, so a payload that
omits `hand` on one run and supplies it on the next is normal. Without COALESCE
the second run would write the value and a third would erase it again.
"""
import pytest

from app.repositories.matches import upsert_match
from app.repositories.players import upsert_player


class _Result:
    @staticmethod
    def scalar_one() -> int:
        return 1


class _Session:
    """Captures the last statement and params instead of touching a database."""

    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: dict[str, object] = {}

    async def execute(self, statement, params: dict[str, object] | None = None):
        self.statements.append(str(statement))
        if params:
            self.params = params
        return _Result()

    @property
    def sql(self) -> str:
        return " ".join(self.statements)


MATCH_COALESCED = (
    "indoor",
    "tournament_id",
    "p1_ranking_points",
    "p2_ranking_points",
    "p1_ranking_movement",
    "p2_ranking_movement",
)


@pytest.mark.anyio
async def test_upsert_match_coalesces_every_new_field():
    db = _Session()
    await upsert_match(
        db, match_key="livetennis:1", match_date=None, tour="atp", p1_id=1, p2_id=2,
        indoor=True, tournament_id="11043",
        p1_ranking_points=7265, p2_ranking_points=0,
        p1_ranking_movement="up", p2_ranking_movement="same",
    )
    for column in MATCH_COALESCED:
        assert f"COALESCE(EXCLUDED.{column}, matches.{column})" in db.sql, column

    assert db.params["indoor"] is True
    assert db.params["tourn_id"] == "11043"
    # 0 is a real point total; it must reach the bind, not be dropped as falsy.
    assert db.params["p2rp"] == 0
    assert db.params["p1rm"] == "up"


@pytest.mark.anyio
async def test_upsert_match_binds_none_when_the_payload_omits_the_fields():
    db = _Session()
    await upsert_match(
        db, match_key="livetennis:2", match_date=None, tour="atp", p1_id=1, p2_id=2,
    )
    for key in ("indoor", "tourn_id", "p1rp", "p2rp", "p1rm", "p2rm"):
        assert db.params[key] is None, key


@pytest.mark.anyio
async def test_upsert_player_coalesces_hand_and_country():
    db = _Session()
    await upsert_player(db, "A Player", "atp", hand="R", country="ITA")
    assert "COALESCE(EXCLUDED.hand, players.hand)" in db.sql
    assert "COALESCE(EXCLUDED.country, players.country)" in db.sql
    assert db.params["hand"] == "R"
    assert db.params["country"] == "ITA"


@pytest.mark.anyio
async def test_upsert_player_binds_none_when_profile_fields_are_absent():
    db = _Session()
    await upsert_player(db, "A Player", "atp")
    assert db.params["hand"] is None
    assert db.params["country"] is None

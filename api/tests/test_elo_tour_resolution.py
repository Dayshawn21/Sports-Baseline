"""
Which TennisAbstract ELO table a player's tour maps to.

The reported bug: Fetch ELO on a Challenger player returned
"Unknown tour 'CHALLENGER' — expected ATP or WTA" without ever scraping.
There is no Challenger ELO page — those men sit in the ATP table — and
livetennisapi files women's 125/ITF events under `challenger` too, so the
label is gender-ambiguous and has to try both.
"""
import asyncio

import pandas as pd
import pytest

from app.ingest import elo


def _table(*names: str) -> pd.DataFrame:
    """Minimal leaderboard: the columns fetch_single_player_elo actually reads."""
    return pd.DataFrame({
        "player": list(names),
        "elo": [1245.0 + i for i in range(len(names))],
        "helo": [1229.0 + i for i in range(len(names))],
        "celo": [1190.0 + i for i in range(len(names))],
        "gelo": [1322.0 + i for i in range(len(names))],
    })


class _Db:
    """Stand-in for AsyncSession — fetch_single_player_elo only commits."""
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


@pytest.fixture
def scraped(monkeypatch):
    """Record which tours were scraped, serving canned tables per tour."""
    calls: list[str] = []
    tables: dict[str, pd.DataFrame] = {}
    upserts: list[tuple] = []

    def fake_scrape(url, tour):
        calls.append(tour)
        if tour not in tables:
            raise RuntimeError(f"no canned table for {tour}")
        return tables[tour], elo.dt.date(2026, 8, 24)

    async def fake_upsert(db, player_id, as_of, e, helo, celo, gelo, source=None):
        upserts.append((player_id, as_of, e, helo, celo, gelo, source))

    monkeypatch.setattr(elo, "scrape_elo", fake_scrape)
    monkeypatch.setattr("app.repositories.players.upsert_elo", fake_upsert)
    return calls, tables, upserts


def _fetch(db, tour, name="Constantin Bittoun Kouzmine", override=None):
    return asyncio.run(elo.fetch_single_player_elo(
        db=db, player_id=1, player_name=name, tour=tour, ta_name_override=override,
    ))


# =============================================================================
# Tour → table mapping
# =============================================================================

@pytest.mark.parametrize("tour,expected", [
    ("ATP", ["ATP"]),
    ("wta", ["WTA"]),
    ("CHALLENGER", ["ATP", "WTA"]),
    ("challenger", ["ATP", "WTA"]),
    ("ITF", []),
    ("", []),
])
def test_elo_tours_for(tour, expected):
    assert elo.elo_tours_for(tour) == expected


def test_elo_tours_for_tolerates_none():
    assert elo.elo_tours_for(None) == []


# =============================================================================
# Challenger resolution — the reported bug
# =============================================================================

def test_challenger_man_is_found_in_the_atp_table(scraped):
    calls, tables, upserts = scraped
    tables["ATP"] = _table("Someone Else", "Constantin Bittoun Kouzmine")
    tables["WTA"] = _table("Aryna Sabalenka")
    db = _Db()

    result = _fetch(db, "CHALLENGER")

    assert result["success"] is True
    assert result["elo"] == 1246.0
    assert calls == ["ATP"]  # found on the first table, WTA never paid for
    assert upserts[0][1] == elo.dt.date(2026, 8, 24)
    assert db.commits == 1


def test_challenger_woman_falls_through_to_the_wta_table(scraped):
    """WTA 125 events are filed under `challenger`, so ATP-only would miss her."""
    calls, tables, upserts = scraped
    tables["ATP"] = _table("Constantin Bittoun Kouzmine")
    tables["WTA"] = _table("Someone Else", "Lois Boisson")
    db = _Db()

    result = _fetch(db, "CHALLENGER", name="Lois Boisson")

    assert result["success"] is True
    assert result["elo"] == 1246.0
    assert calls == ["ATP", "WTA"]


def test_challenger_reports_both_tables_when_the_name_is_absent(scraped):
    _, tables, upserts = scraped
    tables["ATP"] = _table("Someone Else")
    tables["WTA"] = _table("Someone Else Entirely")
    db = _Db()

    result = _fetch(db, "CHALLENGER", name="Nobody At All")

    assert result["success"] is False
    assert "ATP/WTA" in result["error"]
    assert upserts == [] and db.commits == 0


def test_the_name_override_is_what_gets_matched(scraped):
    _, tables, _ = scraped
    tables["ATP"] = _table("Constantin Bittoun Kouzmine")
    tables["WTA"] = _table("Nobody")

    result = _fetch(db=_Db(), tour="CHALLENGER", name="C. Bittoun-Kouzmine",
                    override="Constantin Bittoun Kouzmine")

    assert result["success"] is True


# =============================================================================
# Unmapped tours and scrape failures
# =============================================================================

def test_an_unmapped_tour_still_short_circuits(scraped):
    calls, _, _ = scraped

    result = _fetch(db=_Db(), tour="ITF")

    assert result["success"] is False
    assert "Unknown tour 'ITF'" in result["error"]
    assert calls == []  # no scrape attempted


def test_one_table_failing_does_not_hide_a_hit_in_the_other(scraped):
    calls, tables, _ = scraped
    # ATP raises (no canned table); the player is in WTA.
    tables["WTA"] = _table("Lois Boisson")

    result = _fetch(db=_Db(), tour="CHALLENGER", name="Lois Boisson")

    assert result["success"] is True
    assert calls == ["ATP", "WTA"]


def test_every_table_failing_surfaces_the_scrape_errors(scraped):
    _, tables, _ = scraped  # no canned tables at all — both raise

    result = _fetch(db=_Db(), tour="CHALLENGER")

    assert result["success"] is False
    assert "ATP: failed to scrape" in result["error"]
    assert "WTA: failed to scrape" in result["error"]

import asyncio
from dataclasses import replace

import pytest

from app.core.prop_projection import compute_stat_avg
from app.routers.props import MarketTotal, _enrich, _fetch_market_totals
from tests.test_props_audit_projection import _Rows, _prop, _stats


def _row(stat_type: str, line: str, *, win_prob: float = 0.6, total: float | None = 21.5,
         over_prob: float | None = None, tour: str | None = "ATP"):
    prop = replace(_prop(line), stat_type=stat_type, best_of=3, player_tour=tour)
    return _enrich(prop, _stats(), _stats(2), win_prob, market_total_games=total, market_total_over_prob=over_prob)


def test_a_book_line_is_read_as_its_implied_mean():
    row = _row("Total Games", "21.5")
    assert row.market_total_games == 21.5
    assert row.projection_inputs["market_total_games"] == 21.5
    assert row.projection_inputs["market_total_mean"] > 21.5
    assert row.projection_inputs["market_total_price_source"] == "even"
    assert row.stat_avg == pytest.approx(row.projection_inputs["market_total_mean"], abs=0.01)


@pytest.mark.parametrize("stat", ["Total Games Won", "Aces", "Double Faults", "Break Points Won", "Fantasy Score"])
def test_every_totals_based_stat_reads_the_mean_not_the_line(stat):
    row = _row(stat, "5.5")
    mean = row.projection_inputs["market_total_mean"]
    from_mean = compute_stat_avg(stat, _stats(), _stats(2), 0.6, "Hard", mean, 3, tour="ATP")
    from_line = compute_stat_avg(stat, _stats(), _stats(2), 0.6, "Hard", 21.5, 3, tour="ATP")
    assert row.stat_avg == pytest.approx(from_mean, abs=0.01)
    assert from_mean != pytest.approx(from_line, abs=0.01)


def test_an_over_favored_price_raises_the_mean():
    even = _row("Total Games", "21.5")
    over = _row("Total Games", "21.5", over_prob=0.58)
    assert over.projection_inputs["market_total_mean"] > even.projection_inputs["market_total_mean"]
    assert over.projection_inputs["market_total_price_source"] == "devigged"


def test_no_book_total_keeps_the_model_total():
    row = _row("Total Games", "21.5", total=None)
    assert "market_total_mean" not in row.projection_inputs
    assert row.projection_source == "model_total"


def test_tour_reaches_the_projection():
    atp = _row("Double Faults", "3.5", tour="ATP")
    wta = _row("Double Faults", "3.5", tour="WTA")
    assert atp.stat_avg != wta.stat_avg


def test_market_total_devigs_its_prices():
    assert MarketTotal(21.5, -110, -110).p_over == pytest.approx(0.5)
    assert MarketTotal(21.5, -150, 120).p_over > 0.5
    assert MarketTotal(21.5, None, -110).p_over is None


class _Db:
    async def execute(self, query, params):
        self.query = str(query)
        return _Rows([(10, 22.5, -125, 105), (11, 20.5, None, None)])


def test_market_totals_read_line_and_prices():
    db = _Db()
    totals = asyncio.run(_fetch_market_totals(db, [replace(_prop(), match_id=10), replace(_prop(), match_id=11)]))
    assert "mo.p1_odds, mo.p2_odds" in db.query
    assert totals[10] == MarketTotal(22.5, -125, 105)
    assert totals[11].p_over is None

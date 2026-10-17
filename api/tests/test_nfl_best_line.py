from datetime import UTC, datetime, timedelta

from app.core.nfl_best_line import Quote, best_lines
from app.core.odds import implied_prob_from_american

NOW = datetime(2026, 10, 7, 16, tzinfo=UTC)


def _quote(book: str, market: str, line: float | None, first: int, second: int, hours_old: float = 1, provider: str = "odds_api_io") -> Quote:
    return Quote(book, provider, market, line, first, second, implied_prob_from_american(first, second)[0], NOW - timedelta(hours=hours_old))


# TB at DAL as stored on 2026-10-07 (36a archive); DAL is home.
TB_AT_DAL = [
    _quote("pinnacle", "moneyline", None, -446, 353, provider="the_odds_api_eu"),
    _quote("pinnacle", "spread", -8.0, -103, -110, provider="the_odds_api_eu"),
    _quote("pinnacle", "total", 47.5, -108, -106, provider="the_odds_api_eu"),
    _quote("draftkings", "moneyline", None, -476, 360),
    _quote("draftkings", "spread", -8.5, -116, -105),
    _quote("draftkings", "total", 47.5, -116, -105),
    _quote("bet365", "moneyline", None, -500, 370),
    _quote("bet365", "spread", -9.5, -108, -114),
    _quote("bet365", "total", 47.5, -111, -110),
    _quote("draftkings", "spread", -9.5, -110, -110, hours_old=150, provider="the_odds_api_us"),
]


def _market(markets, name):
    return next(market for market in markets if market.market == name)


def test_tb_at_dal_spread_names_each_sides_best_book_and_points_against_pinnacle() -> None:
    spread = _market(best_lines(TB_AT_DAL, NOW), "spread")

    assert (spread.fair.source, spread.fair.line) == ("pinnacle", -8.0)
    home, away = spread.sides
    assert (home.side, home.line, home.odds, home.book, home.points_vs_fair, home.ev_pct) == ("home", -8.5, -116, "draftkings", -0.5, None)
    assert (away.side, away.line, away.odds, away.book, away.points_vs_fair, away.ev_pct) == ("away", -9.5, -114, "bet365", 1.5, None)


def test_tb_at_dal_moneyline_reads_ev_against_pinnacles_devigged_price() -> None:
    moneyline = _market(best_lines(TB_AT_DAL, NOW), "moneyline")

    home, away = moneyline.sides
    assert (home.odds, home.book, away.odds, away.book) == (-476, "draftkings", 370, "bet365")
    assert abs((1 - moneyline.fair.first_probability) - 0.213) < 0.001
    assert abs(away.ev_pct) < 0.005 and away.points_vs_fair is None


def test_a_total_at_the_fair_line_takes_the_better_price_per_side() -> None:
    total = _market(best_lines(TB_AT_DAL, NOW), "total")

    over, under = total.sides
    assert (over.side, over.book, over.odds, under.side, under.book, under.odds) == ("over", "bet365", -111, "under", "draftkings", -105)
    assert over.ev_pct is not None and over.points_vs_fair is None


def test_totals_prefer_the_lower_line_for_overs_and_the_higher_for_unders() -> None:
    quotes = [_quote("a", "total", 46.5, -120, 100), _quote("b", "total", 47.5, 100, -120)]

    over, under = _market(best_lines(quotes, NOW), "total").sides
    assert (over.book, under.book) == ("a", "b")


def test_pinnacle_is_never_a_candidate_and_a_stale_quote_is_dropped() -> None:
    quotes = [
        _quote("pinnacle", "moneyline", None, -100, 120, provider="the_odds_api_eu"),
        _quote("draftkings", "moneyline", None, -110, -110, hours_old=37),
        _quote("bet365", "moneyline", None, -105, -115),
    ]

    moneyline = _market(best_lines(quotes, NOW), "moneyline")
    assert {side.book for side in moneyline.sides} == {"bet365"}


def test_a_newer_quote_from_the_same_book_replaces_the_older_one() -> None:
    quotes = [_quote("draftkings", "spread", -3.0, -110, -110, hours_old=2), _quote("draftkings", "spread", -2.5, -110, -110, hours_old=1)]

    assert [side.line for side in _market(best_lines(quotes, NOW), "spread").sides] == [-2.5, -2.5]


def test_without_pinnacle_two_books_at_one_line_give_a_consensus_fair() -> None:
    quotes = [_quote("a", "spread", -3.0, -110, -110), _quote("b", "spread", -3.0, -120, 100), _quote("c", "spread", -3.5, -105, -115)]

    spread = _market(best_lines(quotes, NOW), "spread")
    assert (spread.fair.source, spread.fair.line) == ("consensus", -3.0)
    assert spread.sides[0].book == "a" and spread.sides[0].ev_pct is not None
    assert spread.sides[1].book == "c" and spread.sides[1].points_vs_fair == 0.5


def test_a_lone_book_has_no_fair_and_no_comparison() -> None:
    spread = _market(best_lines([_quote("a", "spread", -3.0, -110, -110)], NOW), "spread")

    assert spread.fair is None
    assert all(side.ev_pct is None and side.points_vs_fair is None for side in spread.sides)


def test_a_price_tie_goes_to_the_newer_quote_then_the_book_name() -> None:
    quotes = [_quote("b", "moneyline", None, 150, -170, hours_old=1), _quote("a", "moneyline", None, 150, -170, hours_old=1), _quote("c", "moneyline", None, 150, -170, hours_old=3)]

    assert _market(best_lines(quotes, NOW), "moneyline").sides[0].book == "a"


def test_no_fresh_candidate_means_no_market() -> None:
    assert best_lines([_quote("pinnacle", "spread", -3.0, -110, -110, provider="the_odds_api_eu")], NOW) == []

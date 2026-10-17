"""The stored match total must be the match's main games line, not a ladder rung, an
aces or team total, or the first-set total. Market shapes are trimmed copies of
Odds-API.io Bet365 payloads fetched on 2026-09-25."""
from app.ingest.odds_api import BOOK_CONFIGS, _bookmaker_market_rows, _parse_draftkings

GAMES = {"name": "Totals (Games)", "odds": [{"hdp": 24.5, "over": "1.83", "under": "1.83"}]}
FIRST_SET = {"name": "Totals 1st Set", "odds": [
    {"hdp": 9.5, "over": "1.40", "under": "2.75"},
    {"hdp": 10.5, "over": "2.20", "under": "1.61"},
]}
ACES = {"name": "Totals (Aces)", "odds": [
    {"hdp": 19.5, "over": "1.25"}, {"hdp": 24.5, "over": "1.61"}, {"hdp": 29.5, "over": "2.20"},
]}
DOUBLE_FAULTS = {"name": "Totals (Double Faults)", "odds": [{"hdp": 7.5, "over": "1.90"}, {"hdp": 9.5, "over": "3.40"}]}
TEAM_GAMES = {"name": "Team Total (Games) Home", "odds": [{"hdp": 13.5, "over": "2.20", "under": "1.61"}]}
TEAM_ACES = {"name": "Team Total (Aces) Away", "odds": [{"hdp": 9.5, "over": "2.10"}, {"hdp": 14.5, "over": "5.00"}]}


def _total(markets: list[dict]) -> tuple:
    parsed = _parse_draftkings(markets)
    return parsed["total_line"], parsed["total_over"], parsed["total_under"]


def test_the_games_total_is_kept_whatever_surrounds_it():
    for order in (
        [GAMES, FIRST_SET, ACES, DOUBLE_FAULTS, TEAM_GAMES, TEAM_ACES],
        [FIRST_SET, ACES, DOUBLE_FAULTS, TEAM_GAMES, TEAM_ACES, GAMES],
    ):
        assert _total(order) == (24.5, -120, -120)


def test_other_totals_alone_yield_no_match_total():
    assert _total([FIRST_SET, ACES, DOUBLE_FAULTS, TEAM_GAMES, TEAM_ACES]) == (None, None, None)


def test_the_first_set_total_is_never_stored_as_the_match_total():
    assert _total([FIRST_SET]) == (None, None, None)


def test_the_balanced_line_wins_over_the_one_nearest_21_5():
    ladder = {"name": "Total Games", "odds": [
        {"hdp": 21.5, "over": "1.40", "under": "2.90"},
        {"hdp": 23.5, "over": "1.91", "under": "1.91"},
        {"hdp": 25.5, "over": "2.75", "under": "1.44"},
    ]}
    assert _total([ladder])[0] == 23.5


def test_one_sided_rungs_are_not_a_main_line():
    rungs = {"name": "Total Games", "odds": [{"hdp": 21.5, "over": "1.90"}, {"hdp": 22.5, "over": "2.10"}]}
    assert _total([rungs]) == (None, None, None)


def test_moneyline_still_parses_beside_totals():
    parsed = _parse_draftkings([{"name": "ML", "odds": [{"home": "1.50", "away": "2.60"}]}, ACES, GAMES])
    assert (parsed["p1_odds"], parsed["p2_odds"]) == (-200, 160)


def test_totals_keep_over_and_under_when_the_away_player_is_p1():
    bet365 = next(c for c in BOOK_CONFIGS if c.canonical_name == "bet365")
    lopsided = {"name": "Totals (Games)", "odds": [{"hdp": 21.5, "over": "1.72", "under": "2.00"}]}
    for home_is_p1 in (True, False):
        total = next(r for r in _bookmaker_market_rows(bet365, [lopsided], home_is_p1) if r.market == "total_games")
        assert (total.line, total.p1_odds, total.p2_odds) == (21.5, -139, 100)

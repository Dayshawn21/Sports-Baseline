import argparse
from datetime import date

import pytest

from app.backtest.nba_minutes import ScoredPair, parse_season, report
from app.core.nba_projection_backtest import NbaReplayCase


def _case(player: int, projection: float, actual: float) -> NbaReplayCase:
    return NbaReplayCase(
        player_id=player, game_id=player, game_date=date(2025, 1, 5), game_type="REG", market="rebounds",
        prior_minutes=30.0, projection=projection, actual=actual,
    )


def _pairs() -> list[ScoredPair]:
    pairs = []
    for player in range(300):
        actual = 7.0 if player % 2 else 3.0
        # Closer on every over, unchanged on every under: 12.5% lower MAE.
        candidate = 5.5 if actual == 7.0 else 5.0
        pairs.append(ScoredPair("rebounds", 2.0, _case(player, 5.0, actual), _case(player, candidate, actual)))
    pairs.append(ScoredPair("rebounds", 0.0, _case(900, 5.0, 4.0), _case(900, 5.0, 4.0)))
    return pairs


def test_report_prints_the_gate_row_the_unaffected_check_and_the_passing_markets() -> None:
    text = report(0.75, 4321, _pairs(), _pairs())

    assert "k = 0.7500, fitted on 4321 2023-24 player-games" in text
    assert "  rebounds                      301      300    2.000    1.750  -12.50%   -0.250  0.014    +0.00    +0.25  adopt" in text
    assert "Unaffected cases: 1 (1 with no minutes change, projection identical to nba-reference-v1: yes)" in text
    assert "pre-registered in 3a886a6f" in text
    assert "Oracle availability (diagnostic, leaks the game's own box score, no verdict)" in text
    assert "  points                          0        0  no affected cases" in text
    assert text.endswith("Markets passing to 65b: rebounds")


def test_report_says_65_closes_when_no_market_passes() -> None:
    worse = [ScoredPair("rebounds", 2.0, p.candidate, p.reference) for p in _pairs()[:300]]

    assert report(0.75, 4321, worse, worse).endswith("Markets passing to 65b: none: 65 closes at 65a")


@pytest.mark.parametrize("season", [2025, 2026, 2023])
def test_only_the_development_season_is_accepted(season: int) -> None:
    with pytest.raises(SystemExit):
        parse_season(argparse.ArgumentParser(), season)
    assert parse_season(argparse.ArgumentParser(), 2024) == 2024

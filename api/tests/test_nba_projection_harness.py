import argparse
from datetime import date

import pytest

from app.backtest.nba_projections import parse_arms, report
from app.core.nba_projection_backtest import NbaReplayCase


def _case(player_id: int, projection: float, actual: float, prior_minutes: float = 30.0) -> NbaReplayCase:
    return NbaReplayCase(
        player_id=player_id, game_id=1, game_date=date(2025, 1, 5), game_type="REG", market="rebounds",
        prior_minutes=prior_minutes, projection=projection, actual=actual,
    )


def _arms() -> dict[str, list[NbaReplayCase]]:
    actuals = [7.0 if player_id % 2 else 3.0 for player_id in range(300)]
    reference = [_case(player_id, 5.0, actual) for player_id, actual in enumerate(actuals)]
    # Closer on every over, unchanged on every under: 12.5% lower MAE.
    last_10 = [_case(player_id, 5.5 if actual == 7.0 else 5.0, actual) for player_id, actual in enumerate(actuals)]
    return {"reference": reference, "last_10": last_10}


def test_report_prints_metrics_a_paired_row_and_a_verdict() -> None:
    text = report(2024, _arms())

    assert "rebounds / all                          300     2.00     2.00    +0.00    50.0%" in text
    assert "rebounds / 28+ min                      300     2.00     2.00    +0.00    50.0%" in text
    assert "rebounds                      300     2.000     1.750  -12.50%   -0.250   0.014  adopt" in text
    assert "pre-registered 2026-10-06" in text
    assert "2024-25 (development" in text


def test_report_names_the_holdout_and_splits_minutes_buckets() -> None:
    cases = [_case(1, 5.0, 4.0, prior_minutes=20.0), _case(2, 5.0, 8.0, prior_minutes=27.9)]
    text = report(2025, {"reference": cases})

    assert "2025-26 (HOLDOUT: each candidate arm is scored here once" in text
    assert "rebounds / 20-28 min                      2" in text
    assert "rebounds / 28+ min" not in text
    assert "against reference" not in text


def test_arms_must_be_known_and_include_reference() -> None:
    parser = argparse.ArgumentParser()
    assert parse_arms(parser, "reference, last_10") == ["reference", "last_10"]
    with pytest.raises(SystemExit):
        parse_arms(parser, "reference,minutes")
    with pytest.raises(SystemExit):
        parse_arms(parser, "last_10")

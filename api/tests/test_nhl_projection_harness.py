import datetime as dt

import pytest

from app.backtest.nhl_projections import (
    PREREGISTRATION_COMMIT, parse_arms, report, season_label, seasons_to_read,
)
from app.core.nhl_projection_backtest import NhlReplayCase


def case(game_id: int, market: str, projection: float, actual: float, toi: float | None = 14.0) -> NhlReplayCase:
    return NhlReplayCase(
        player_id=1, game_id=game_id, game_date=dt.date(2024, 11, 1), game_type="REG", market=market,
        prior_toi_minutes=toi, projection=projection, actual=actual,
    )


def test_only_the_development_season_runs_without_the_flag() -> None:
    assert seasons_to_read(2024, holdout=False) == (2023, 2024)


@pytest.mark.parametrize("season", [2022, 2023, 2025, 2026, 2027])
def test_every_other_season_needs_the_flag(season: int) -> None:
    with pytest.raises(ValueError, match="only 2024-25 runs without --holdout"):
        seasons_to_read(season, holdout=False)


@pytest.mark.parametrize("season", [2025, 2026, 2027])
def test_the_flag_unlocks_the_holdout_and_later_seasons(season: int) -> None:
    assert seasons_to_read(season, holdout=True) == (season - 1, season)


def test_the_flag_does_not_unlock_seasons_below_the_holdout() -> None:
    with pytest.raises(ValueError, match="--holdout is for 2025-26 or later"):
        seasons_to_read(2023, holdout=True)


def test_arms_must_include_the_reference_and_be_known() -> None:
    assert parse_arms("reference, last_10") == ["reference", "last_10"]
    for bad in ("last_10", "reference,nope", ""):
        with pytest.raises(ValueError, match="arms must include reference"):
            parse_arms(bad)


def test_season_labels_read_as_two_calendar_years() -> None:
    assert (season_label(2024), season_label(2099)) == ("2024-25", "2099-00")


def test_report_names_the_role_rule_commit_and_goalie_caveat() -> None:
    reference = [case(1, "shots_on_goal", 2.0, 3.0)]
    text = report(2024, {"reference": reference})
    assert "2024-25 (development: replay and fit freely)" in text
    assert PREREGISTRATION_COMMIT in text
    assert "Adopt a market only with >= 300 paired holdout cases" in text
    assert "Goalie caveat" in text
    assert "HOLDOUT" not in text


def test_report_marks_the_holdout_season() -> None:
    assert "HOLDOUT: each candidate arm is scored here once" in report(2025, {"reference": [case(1, "hits", 1.0, 1.0)]})


def test_report_tables_hold_metrics_buckets_and_the_paired_verdict() -> None:
    reference = [case(1, "shots_on_goal", 2.0, 3.0), case(2, "shots_on_goal", 2.0, 1.0, toi=17.0)]
    last_10 = [case(1, "shots_on_goal", 3.0, 3.0), case(2, "shots_on_goal", 1.0, 1.0, toi=17.0)]
    lines = report(2024, {"reference": reference, "last_10": last_10}).splitlines()
    assert any(line.strip().startswith("shots_on_goal / all") and line.split()[-5] == "2" for line in lines)
    assert any("shots_on_goal / 12-16 min" in line for line in lines)
    assert any("shots_on_goal / 16+ min" in line for line in lines)
    paired_rows = [line for line in lines if line.startswith("  shots_on_goal ") and "insufficient" in line]
    assert len(paired_rows) == 1 and "-100.00%" in paired_rows[0]
    assert any(line.startswith("Arm last_10 against reference") for line in lines)


def test_goalie_cases_without_a_toi_bucket_still_print_an_all_row() -> None:
    text = report(2024, {"reference": [case(1, "goalie_saves", 25.0, 30.0, toi=None)]})
    assert "goalie_saves / all" in text
    assert "goalie_saves / 12-16 min" not in text

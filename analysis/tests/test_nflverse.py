import pandas as pd
import pytest

from lib import nflverse
from lib import nfl_team_report as report


def schedule(rows):
    """rows: (season, game_type, home, away, home_score, away_score)."""
    frame = pd.DataFrame(rows, columns=["season", "game_type", "home_team", "away_team", "home_score", "away_score"])
    frame["game_id"] = [f"g{i}" for i in range(len(frame))]
    frame["week"] = 1
    return frame[nflverse.SCHEDULE_COLUMNS]


SCHEDULE = schedule([
    (2024, "REG", "A", "B", 20, 10), (2024, "REG", "A", "C", 20, 10), (2024, "REG", "B", "C", 20, 10),
    (2024, "REG", "C", "D", 14, 14), (2024, "REG", "D", "A", None, None),
    (2024, "WC", "B", "C", 21, 17),
    (2024, "DIV", "A", "B", 30, 3),
])


def test_load_schedules_downloads_once_then_reads_the_cache(tmp_path, monkeypatch):
    calls = []

    def fake_download(seasons):
        calls.append(seasons)
        return SCHEDULE.assign(extra="dropped")

    monkeypatch.setattr(nflverse, "_download_schedules", fake_download)
    first = nflverse.load_schedules([2024], data_dir=tmp_path)
    second = nflverse.load_schedules([2024], data_dir=tmp_path)
    assert calls == [[2024]]
    assert list(first.columns) == nflverse.SCHEDULE_COLUMNS
    assert len(second) == len(SCHEDULE)
    assert nflverse.schedule_cache_path([2024], tmp_path).is_file()


def test_load_schedules_refuses_gaps_and_missing_seasons(tmp_path, monkeypatch):
    monkeypatch.setattr(nflverse, "_download_schedules", lambda seasons: SCHEDULE)
    with pytest.raises(ValueError, match="continuous"):
        nflverse.load_schedules([2021, 2023], data_dir=tmp_path)
    with pytest.raises(ValueError, match="no games for seasons \[2025\]"):
        nflverse.load_schedules([2024, 2025], data_dir=tmp_path)


def test_final_wins_counts_ties_as_half_rounded_down_and_skips_unscored_games():
    wins = report.final_wins(SCHEDULE).set_index("team")["wins"].to_dict()
    assert wins == {"A": 2, "B": 1, "C": 0, "D": 0}


def test_bye_teams_count_as_playoff_teams_through_div_games():
    entrants = report.playoff_entrants(SCHEDULE)
    assert sorted(entrants["team"]) == ["A", "B", "C"]


def test_playoff_rate_by_wins_table():
    table = report.playoff_rate_by_wins(SCHEDULE)
    assert table.loc[2].tolist() == [1, 1, 1.0]
    assert table.loc[0, "teams"] == 2
    assert table.loc[0, "rate"] == pytest.approx(0.5)


def test_playoff_rate_clamps_outside_and_interpolates_inside():
    table = pd.DataFrame({"rate": [0.0, 0.5, 1.0]}, index=[4, 6, 8])
    assert report.playoff_rate(table, 2) == 0.0
    assert report.playoff_rate(table, 12) == 1.0
    assert report.playoff_rate(table, 6) == 0.5
    assert report.playoff_rate(table, 7) == pytest.approx(0.75)

import pytest

from app.core.nfl_baseline import (
    CURRENT_SEASON,
    LARGEST_SAMPLE,
    MIN_BASELINE_GAMES,
    NO_DATA,
    PREVIOUS_SEASON,
    BaselineChoice,
    SeasonGames,
    choose_baseline_season,
)


def _seasons(**by_season: int) -> list[SeasonGames]:
    """Build season rows from y2025=12 style kwargs, since 2025=12 is not valid Python."""
    return [SeasonGames(int(season.lstrip("y")), games) for season, games in by_season.items()]


@pytest.mark.parametrize(
    ("case", "line_season", "seasons", "expected"),
    [
        (
            "a full current season is used as-is",
            2025,
            _seasons(y2024=17, y2025=12),
            BaselineChoice(2025, 12, CURRENT_SEASON),
        ),
        (
            "exactly the minimum still qualifies",
            2025,
            _seasons(y2024=17, y2025=MIN_BASELINE_GAMES),
            BaselineChoice(2025, MIN_BASELINE_GAMES, CURRENT_SEASON),
        ),
        (
            "a week-2 player falls back to last season",
            2026,
            _seasons(y2025=16, y2026=1),
            BaselineChoice(2025, 16, PREVIOUS_SEASON),
        ),
        (
            "fallback takes the most recent qualifying season, not the largest",
            2026,
            _seasons(y2023=17, y2024=17, y2025=9, y2026=1),
            BaselineChoice(2025, 9, PREVIOUS_SEASON),
        ),
        (
            "no season qualifies, so the largest sample is used and flagged",
            2026,
            _seasons(y2025=3, y2026=2),
            BaselineChoice(2025, 3, LARGEST_SAMPLE),
        ),
        (
            "a tie on games goes to the more recent season",
            2026,
            _seasons(y2024=2, y2025=2),
            BaselineChoice(2025, 2, LARGEST_SAMPLE),
        ),
        (
            "a rookie present only in the line's season",
            2026,
            _seasons(y2026=6),
            BaselineChoice(2026, 6, CURRENT_SEASON),
        ),
        (
            "a player present in only one earlier season",
            2026,
            _seasons(y2024=11),
            BaselineChoice(2024, 11, PREVIOUS_SEASON),
        ),
        (
            "no stats at all",
            2026,
            [],
            BaselineChoice(None, 0, NO_DATA),
        ),
        (
            "seasons present but every one empty",
            2026,
            _seasons(y2025=0, y2026=0),
            BaselineChoice(None, 0, NO_DATA),
        ),
    ],
)
def test_choose_baseline_season(
    case: str, line_season: int, seasons: list[SeasonGames], expected: BaselineChoice
) -> None:
    assert choose_baseline_season(line_season, seasons) == expected, case


def test_a_season_later_than_the_line_is_not_a_candidate() -> None:
    # Data from after the line cannot exist when the line is priced, so a stray
    # future row must not quietly become the baseline.
    choice = choose_baseline_season(2025, _seasons(y2025=8, y2026=17))

    assert choice == BaselineChoice(2025, 8, CURRENT_SEASON)


def test_only_future_seasons_reads_as_no_data() -> None:
    assert choose_baseline_season(2024, _seasons(y2026=17)).reason == NO_DATA


def test_largest_sample_can_still_select_the_lines_own_season() -> None:
    # The reason is not a proxy for staleness: this baseline is thin, but it is
    # the line's own season, so a caller keying "stale" off the reason would be
    # wrong. Staleness is a season comparison, never a reason lookup.
    choice = choose_baseline_season(2026, _seasons(y2025=2, y2026=3))

    assert choice == BaselineChoice(2026, 3, LARGEST_SAMPLE)
    assert choice.season == 2026

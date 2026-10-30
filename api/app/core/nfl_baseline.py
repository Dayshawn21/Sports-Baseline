"""Choose which season a player's baseline is computed from.

Averaging every loaded season together produces a number that describes no
season in particular: a 2026 line priced against a blend of 2024 and 2025 form
looks current without being current. This module picks one season and says why,
so the caller can report the choice rather than imply it.

This is a selection rule, not a model. Weighting seasons, adjusting for opponent,
and regressing to the mean belong to the projection model (build-plan item 19e),
which will replace `choose_baseline_season` while keeping `BaselineChoice`.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

# v4 and Rec Targets were validated on history from 2024 on. Older seasons
# backfilled for later work (2026-10-29) must not move them under the same version.
PROJECTION_FIRST_HISTORY_SEASON = 2024

# One threshold governs both the baseline choice and the `small_sample` flag, so
# a season can never be good enough to select yet too thin to trust.
MIN_BASELINE_GAMES = 4

# A completed NFL regular season for one player. Fewer games in the line's own
# season means that season is still being played, so the average will move.
FULL_SEASON_GAMES = 17

CURRENT_SEASON = "current_season"
PREVIOUS_SEASON = "previous_season"
LARGEST_SAMPLE = "largest_sample"
NO_DATA = "no_data"
# Anytime TD weights several seasons instead of choosing one; see anytime_td_probability.
BLENDED_SEASONS = "blended_seasons"
# The current and previous season weighted by games (27d); see nfl_season_blend.
CURRENT_PREVIOUS_BLEND = "current_previous_blend"


@dataclass(frozen=True)
class SeasonGames:
    """How many regular-season games a player has in one season."""

    season: int
    games: int


@dataclass(frozen=True)
class BaselineChoice:
    season: int | None
    games: int
    reason: str


def choose_baseline_season(line_season: int, seasons: Sequence[SeasonGames]) -> BaselineChoice:
    """Pick the season a baseline should come from for a line in `line_season`.

    Preference order: the line's own season once it clears `MIN_BASELINE_GAMES`,
    then the most recent earlier season that clears it, then whatever season has
    the most games. The last case is deliberately still a choice rather than a
    refusal: a thin baseline flagged as thin beats no number at all.
    """
    # A season later than the line cannot exist when the line is priced, so it is
    # a data error rather than a candidate. Ignoring it keeps one bad row from
    # silently becoming a player's baseline.
    candidates = [entry for entry in seasons if entry.games > 0 and entry.season <= line_season]
    if not candidates:
        return BaselineChoice(season=None, games=0, reason=NO_DATA)

    qualifying = [entry for entry in candidates if entry.games >= MIN_BASELINE_GAMES]

    for entry in qualifying:
        if entry.season == line_season:
            return BaselineChoice(entry.season, entry.games, CURRENT_SEASON)

    if qualifying:
        best = max(qualifying, key=lambda entry: entry.season)
        return BaselineChoice(best.season, best.games, PREVIOUS_SEASON)

    # Ties go to the more recent season: same evidence, fresher roster and form.
    best = max(candidates, key=lambda entry: (entry.games, entry.season))
    return BaselineChoice(best.season, best.games, LARGEST_SAMPLE)

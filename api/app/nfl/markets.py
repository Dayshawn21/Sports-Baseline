"""Supported NFL player-prop markets and game segments for the first release."""
from __future__ import annotations

from enum import StrEnum

from app.core.prop_sports import SportPropConfig
from app.core.prop_sports import segment_for_league_name as generic_segment_for_league_name


class NflPropSegment(StrEnum):
    """The slice of a game a prop line covers.

    PrizePicks publishes halves, quarters, and season-long totals under the same
    stat_type strings as the full game, so the segment is what keeps a 1249.5
    season receiving-yards line from being read as a full-game line.
    """

    FULL_GAME = "full_game"
    FIRST_HALF = "first_half"
    SECOND_HALF = "second_half"
    Q1 = "q1"
    Q2 = "q2"
    Q3 = "q3"
    Q4 = "q4"
    SEASON = "season"


def segment_for_league_name(name: str) -> NflPropSegment | None:
    """Map a PrizePicks league name to its segment, or None if it is not NFL."""
    segment = generic_segment_for_league_name(name, NFL_PROPS)
    return NflPropSegment(segment) if segment is not None else None


#: The one odds type whose line represents the market's actual estimate. Goblin
#: and demon lines are moved off it deliberately, with the payout adjusted, so a
#: projection compared against them measures the payout ladder, not a mispricing.
STANDARD_ODDS_TYPE = "standard"


class NflPropMarket(StrEnum):
    PASSING_YARDS = "passing_yards"
    PASSING_ATTEMPTS = "passing_attempts"
    PASSING_COMPLETIONS = "passing_completions"
    RUSHING_YARDS = "rushing_yards"
    RUSHING_ATTEMPTS = "rushing_attempts"
    RECEIVING_YARDS = "receiving_yards"
    RECEPTIONS = "receptions"
    ANYTIME_TOUCHDOWN = "anytime_touchdown"
    FANTASY_POINTS = "fantasy_points"
    RECEIVING_TARGETS = "receiving_targets"


SUPPORTED_NFL_PROP_MARKETS = frozenset(NflPropMarket)

# v4's fitted inputs and forward sample must not grow when another model adds a market.
NFL_V4_PROP_MARKETS = frozenset({
    NflPropMarket.PASSING_YARDS,
    NflPropMarket.PASSING_ATTEMPTS,
    NflPropMarket.PASSING_COMPLETIONS,
    NflPropMarket.RUSHING_YARDS,
    NflPropMarket.RUSHING_ATTEMPTS,
    NflPropMarket.RECEIVING_YARDS,
    NflPropMarket.RECEPTIONS,
    NflPropMarket.ANYTIME_TOUCHDOWN,
    NflPropMarket.FANTASY_POINTS,
})


class NflLineOnlyMarket(StrEnum):
    """Markets stored for line history only (item 34): never projected, graded or shown.

    Each settles from columns `nfl_player_weekly_stats` already holds, so a later
    item can grade the whole stored history. The values are stored and never renamed.
    """

    PASSING_TOUCHDOWNS = "passing_touchdowns"
    INTERCEPTIONS = "interceptions"
    RUSHING_RECEIVING_YARDS = "rushing_receiving_yards"
    PASSING_RUSHING_YARDS = "passing_rushing_yards"
    PASSING_RUSHING_RECEIVING_TOUCHDOWNS = "passing_rushing_receiving_touchdowns"
    # 34b: settle on fg_made, 3 * fg_made + pat_made, and punts.
    FIELD_GOALS_MADE = "field_goals_made"
    KICKING_POINTS = "kicking_points"
    PUNTS = "punts"


NFL_PROPS = SportPropConfig(
    code="nfl",
    league_prefix="NFL",
    segment_suffixes={
        "1H": NflPropSegment.FIRST_HALF,
        "2H": NflPropSegment.SECOND_HALF,
        "1Q": NflPropSegment.Q1,
        "2Q": NflPropSegment.Q2,
        "3Q": NflPropSegment.Q3,
        "4Q": NflPropSegment.Q4,
        "SZN": NflPropSegment.SEASON,
    },
    board_segments=frozenset({NflPropSegment.FULL_GAME, NflPropSegment.FIRST_HALF, NflPropSegment.Q1}),
    market_aliases={
        "passing yards": NflPropMarket.PASSING_YARDS,
        "pass yards": NflPropMarket.PASSING_YARDS,
        "pass attempts": NflPropMarket.PASSING_ATTEMPTS,
        "passing attempts": NflPropMarket.PASSING_ATTEMPTS,
        "pass completions": NflPropMarket.PASSING_COMPLETIONS,
        "passing completions": NflPropMarket.PASSING_COMPLETIONS,
        "rushing yards": NflPropMarket.RUSHING_YARDS,
        "rush yards": NflPropMarket.RUSHING_YARDS,
        "rush attempts": NflPropMarket.RUSHING_ATTEMPTS,
        "rushing attempts": NflPropMarket.RUSHING_ATTEMPTS,
        "receiving yards": NflPropMarket.RECEIVING_YARDS,
        "receptions": NflPropMarket.RECEPTIONS,
        "fantasy score": NflPropMarket.FANTASY_POINTS,
        "fantasy points": NflPropMarket.FANTASY_POINTS,
        "anytime touchdowns": NflPropMarket.ANYTIME_TOUCHDOWN,
        "anytime tds": NflPropMarket.ANYTIME_TOUCHDOWN,
        # Exact names from the 2026-10-05 board; the "(Combo)" variants stay unmapped.
        "rec targets": NflPropMarket.RECEIVING_TARGETS,
        "pass tds": NflLineOnlyMarket.PASSING_TOUCHDOWNS,
        "int": NflLineOnlyMarket.INTERCEPTIONS,
        "rush+rec yds": NflLineOnlyMarket.RUSHING_RECEIVING_YARDS,
        "pass+rush yds": NflLineOnlyMarket.PASSING_RUSHING_YARDS,
        "pass+rush+rec tds": NflLineOnlyMarket.PASSING_RUSHING_RECEIVING_TOUCHDOWNS,
        "fg made": NflLineOnlyMarket.FIELD_GOALS_MADE,
        "kicking points": NflLineOnlyMarket.KICKING_POINTS,
        "punts": NflLineOnlyMarket.PUNTS,
    },
    period_label="week",
)

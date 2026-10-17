"""Pure math for comparing NFL game-line models against the closing market.

Every line here follows the NFLverse convention: `spread_line` is the expected
home margin, so a positive line means the home team is favored.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.nfl_elo import NFL_ELO_V1, NflEloGame, expected_home_win_probability
from app.core.odds import implied_prob_from_american

# FiveThirtyEight's NFL conversion: 25 ELO points are worth one point of margin.
ELO_POINTS_PER_MARGIN = 25.0


@dataclass(frozen=True)
class NflGameLineGame:
    """A stored game with its NFLverse closing lines and context; any value may be missing."""

    game: NflEloGame
    spread_line: float | None
    total_line: float | None
    home_moneyline: int | None
    away_moneyline: int | None
    roof: str | None = None
    temp: int | None = None
    wind: int | None = None
    home_rest: int | None = None
    away_rest: int | None = None


def elo_margin(home_elo: float, away_elo: float, home_field: float) -> float:
    """Expected home margin in points, on the same scale as `spread_line`."""
    return (home_elo + home_field - away_elo) / ELO_POINTS_PER_MARGIN


def market_home_probability(home_moneyline: int | None, away_moneyline: int | None) -> float | None:
    """De-vigged closing home win probability, or None when either price is unusable."""
    if not home_moneyline or not away_moneyline:
        return None
    return implied_prob_from_american(home_moneyline, away_moneyline)[0]


def blend(model: float, market: float, weight: float) -> float:
    """Move `weight` of the way from the market toward the model."""
    return weight * model + (1 - weight) * market


def mae(predictions: list[float], actuals: list[float]) -> float:
    if not predictions or len(predictions) != len(actuals):
        raise ValueError("mae needs one actual per prediction and at least one of each")
    return sum(abs(p - a) for p, a in zip(predictions, actuals)) / len(predictions)


@dataclass(frozen=True)
class NflGameModelLine:
    """The display-only game model; `home_spread` uses the book sign, unlike `elo_margin`."""

    home_elo: float
    away_elo: float
    home_win_probability: float
    # Negative when home is favored, the same sign as a sportsbook's home spread.
    home_spread: float
    total: float
    market_home_win_probability: float | None


def game_model_line(
    home_elo: float, away_elo: float, expected_total: float,
    home_moneyline: int | None, away_moneyline: int | None,
) -> NflGameModelLine:
    """`nfl-elo-v1` side and 24b scoring-rating total, beside the displayed book's price."""
    return NflGameModelLine(
        home_elo=home_elo, away_elo=away_elo,
        home_win_probability=expected_home_win_probability(home_elo, away_elo, NFL_ELO_V1.home_field),
        home_spread=-elo_margin(home_elo, away_elo, NFL_ELO_V1.home_field),
        total=expected_total,
        market_home_win_probability=market_home_probability(home_moneyline, away_moneyline),
    )


@dataclass(frozen=True)
class PickRecord:
    hits: int
    misses: int
    pushes: int

    @property
    def picks(self) -> int:
        """Decided picks; pushes return the stake, so they count as neither."""
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float | None:
        return self.hits / self.picks if self.picks else None


def pick_record(
    predictions: list[float], lines: list[float], actuals: list[float], threshold: float,
) -> PickRecord:
    """Grade the side the model takes wherever it differs from the line by at least `threshold`.

    Works for spreads (actual home margin against `spread_line`) and totals
    (actual points against `total_line`): the model's side wins when the result
    lands on the same side of the line as the model did.
    """
    hits = misses = pushes = 0
    for prediction, line, actual in zip(predictions, lines, actuals, strict=True):
        disagreement = prediction - line
        # Rounded so a blend landing a float hair under the threshold still counts.
        if round(abs(disagreement), 9) < threshold:
            continue
        result = actual - line
        if result == 0:
            pushes += 1
        elif (result > 0) == (disagreement > 0):
            hits += 1
        else:
            misses += 1
    return PickRecord(hits, misses, pushes)

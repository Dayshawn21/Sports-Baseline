"""Pure parsing and pricing for The Odds API NFL player yes/no prop markets."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from statistics import median
from typing import Mapping, Sequence

from app.core.odds import american_to_prob, devig_two_way
from app.nfl.markets import NflPropMarket, NflPropSegment


@dataclass(frozen=True)
class NflBookPropPrice:
    book: str
    market_key: str
    player_name: str
    yes_odds: int
    no_odds: int | None
    market_prob: float
    # A Yes-only book cannot be de-vigged: several players can score, so the Yes
    # prices across a game do not sum to one and reveal no margin.
    includes_margin: bool
    raw_market: dict[str, object]


@dataclass(frozen=True)
class NflPropConsensus:
    probability: float
    book_count: int
    includes_margin: bool


def _american(value: object) -> int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number) or abs(number) < 100:
        return None
    return round(number)


def _book_price(book: str, market_key: str, player: str, yes: int, no: int | None, raw: Mapping[str, object]) -> NflBookPropPrice:
    if no is None:
        return NflBookPropPrice(book, market_key, player, yes, None, american_to_prob(yes), True, dict(raw))
    probability, _ = devig_two_way(american_to_prob(yes), american_to_prob(no))
    return NflBookPropPrice(book, market_key, player, yes, no, probability, False, dict(raw))


def _sides_by_player(outcomes: object) -> dict[str, dict[str, int]]:
    sides: dict[str, dict[str, int]] = {}
    if not isinstance(outcomes, list):
        return sides
    for outcome in outcomes:
        if not isinstance(outcome, Mapping):
            continue
        side = str(outcome.get("name") or "").strip().casefold()
        player = " ".join(str(outcome.get("description") or "").split())
        price = _american(outcome.get("price"))
        if side in ("yes", "no") and player and price is not None:
            sides.setdefault(player, {}).setdefault(side, price)
    return sides


def parse_yes_no_props(bookmakers: object, market_keys: Sequence[str]) -> list[NflBookPropPrice]:
    """One price per book per player for the requested yes/no markets."""
    if not isinstance(bookmakers, list):
        return []
    wanted = set(market_keys)
    prices: list[NflBookPropPrice] = []
    for bookmaker in bookmakers:
        if not isinstance(bookmaker, Mapping) or not isinstance(bookmaker.get("markets"), list):
            continue
        book = str(bookmaker.get("key") or "")
        for raw_market in bookmaker["markets"]:
            if not isinstance(raw_market, Mapping) or raw_market.get("key") not in wanted:
                continue
            for player, sides in _sides_by_player(raw_market.get("outcomes")).items():
                if "yes" in sides:
                    prices.append(_book_price(book, str(raw_market["key"]), player, sides["yes"], sides.get("no"), raw_market))
    return prices


@dataclass(frozen=True)
class NflSlateBookOdds:
    probability: float
    book_count: int
    includes_margin: bool
    fetched_at: datetime


def slate_book_odds(
    market: str, segment: str, book_rows: Sequence[tuple[float, bool, datetime]],
) -> NflSlateBookOdds | None:
    """Sportsbook consensus for a slate line, only where the markets mean the same thing.

    Book anytime-TD prices cover the full game, so a half or quarter TD line gets none.
    """
    if market != NflPropMarket.ANYTIME_TOUCHDOWN or segment != NflPropSegment.FULL_GAME:
        return None
    result = consensus([(probability, includes_margin) for probability, includes_margin, _ in book_rows])
    if result is None:
        return None
    return NflSlateBookOdds(
        result.probability, result.book_count, result.includes_margin,
        max(fetched_at for _, _, fetched_at in book_rows),
    )


_NORMALIZE_TOLERANCE = 1e-9
_NORMALIZE_MAX_ITERATIONS = 200

# Least-squares fit of distinct anytime-TD scorers against final combined points,
# over the 544 completed 2024 and 2025 regular-season games that have weekly
# stats loaded (mean 45.92 points, 4.094 scorers). Earlier seasons hold no
# weekly stats, so they are not in the fit.
SCORERS_INTERCEPT = -0.3908
SCORERS_PER_POINT = 0.09765
# A game always prices someone to score, and the fit is only linear over the
# range it was measured on; it reaches zero around 4 points.
MIN_EXPECTED_SCORERS = 1.0


def expected_distinct_scorers(total_line: float | None) -> float | None:
    """Players expected to score a touchdown in a game with this market total.

    The target the Yes-only prices are normalized down to. Fitted against final
    points rather than market totals, which is sound only because the
    relationship is linear: the expectation of a linear function is that
    function of the expectation, so feeding a forecast total returns the
    expected scorer count for that forecast.

    None without a total, so a game the book has not priced gets no
    normalization instead of a guessed one.
    """
    if total_line is None or total_line <= 0.0:
        return None
    return max(SCORERS_INTERCEPT + SCORERS_PER_POINT * total_line, MIN_EXPECTED_SCORERS)


def normalize_one_way(probabilities: Sequence[float], target: float) -> list[float]:
    """Scale Yes-only prices down to `target` by raising each to a common power.

    Anytime-TD prices carry the book's margin and several players can score, so
    the raw probabilities sum to more than the expected number of scorers. The
    exponent form is used instead of multiplying by `target / total` because
    proportional scaling shifts every price by the same ratio, which moves a
    heavy favourite far more in absolute terms than the tail and can push it
    past 1.0. Raising to a power `k > 1` leaves the ordering intact and pulls
    long shots down harder, which is how books build the margin in the first
    place.
    """
    scalable = [index for index, value in enumerate(probabilities) if 0.0 < value < 1.0]
    total = sum(probabilities[index] for index in scalable)
    # Never inflate: a book at or under the target has no margin to remove.
    if not scalable or target <= 0.0 or total <= target:
        return list(probabilities)

    low, high = 1.0, 2.0
    while sum(probabilities[index] ** high for index in scalable) > target:
        high *= 2.0
        if high > 1 << 20:
            return list(probabilities)
    for _ in range(_NORMALIZE_MAX_ITERATIONS):
        power = (low + high) / 2
        if abs(sum(probabilities[index] ** power for index in scalable) - target) < _NORMALIZE_TOLERANCE:
            break
        if sum(probabilities[index] ** power for index in scalable) > target:
            low = power
        else:
            high = power

    normalized = list(probabilities)
    for index in scalable:
        normalized[index] = probabilities[index] ** power
    return normalized


def devigged_book_probabilities(
    player_probabilities: Mapping[int, float], total_line: float | None,
) -> dict[int, float]:
    """One game's Yes-only consensus prices with the book's margin removed.

    Keyed by player so a player holding several lines in the game (0.5 standard
    plus 1.5 and 2.5 demons) contributes one price to the sum and receives one
    normalized value. Summing lines instead would overstate the game by roughly
    the number of lines per player.

    Empty when the game has no market total, since the target is what the
    margin is measured against.
    """
    target = expected_distinct_scorers(total_line)
    if target is None or not player_probabilities:
        return {}
    players = list(player_probabilities)
    normalized = normalize_one_way([player_probabilities[player] for player in players], target)
    return dict(zip(players, normalized))


def consensus(book_prices: Sequence[tuple[float, bool]]) -> NflPropConsensus | None:
    """Median of per-book (probability, includes_margin) pairs for one player."""
    if not book_prices:
        return None
    return NflPropConsensus(
        round(median(probability for probability, _ in book_prices), 4),
        len(book_prices),
        any(includes_margin for _, includes_margin in book_prices),
    )

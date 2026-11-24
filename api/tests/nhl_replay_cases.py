import datetime as dt
from math import exp

from app.core.nhl_projection_backtest import NhlReplayCase
from app.nhl.markets import NhlLineOnlyMarket


def poisson_actuals(mean: float, n: int) -> list[float]:
    """A stratified Poisson sample: the quantile at each of n evenly spaced probabilities."""
    actuals, k, mass = [], 0, exp(-mean)
    cumulative = mass
    for i in range(n):
        level = (i + 0.5) / n
        while cumulative < level:
            k += 1
            mass *= mean / k
            cumulative += mass
        actuals.append(float(k))
    return actuals


def weekly_cases(
    mean: float, n: int, market: NhlLineOnlyMarket = NhlLineOnlyMarket.GOALS,
) -> list[NhlReplayCase]:
    """One case per week, so ISO-week parity alternates case by case."""
    return [
        NhlReplayCase(
            player_id=index, game_id=index, game_date=dt.date(2024, 10, 7) + dt.timedelta(days=7 * index),
            game_type="REG", market=market.value, prior_toi_minutes=18.0, projection=mean, actual=actual,
        )
        for index, actual in enumerate(poisson_actuals(mean, n))
    ]

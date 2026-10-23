"""Calendar weeks for sports whose first week contains opening night."""
from collections.abc import Iterable
from datetime import date, timedelta


def opening_night(regular_season_dates: Iterable[date]) -> date:
    return min(regular_season_dates)


def regular_season_week(game_date: date, opening: date) -> int:
    """Monday-to-Sunday week number, where week 1 holds opening night."""
    first_monday = opening - timedelta(days=opening.weekday())
    if game_date < first_monday:
        raise ValueError(f"{game_date} is before the week of opening night {opening}")
    return (game_date - first_monday).days // 7 + 1

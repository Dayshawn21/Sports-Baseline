"""Date selection shared by daily sport slates."""
from __future__ import annotations

import bisect
import datetime as dt
from collections.abc import Sequence


def slate_date(requested: dt.date | None, today: dt.date, game_dates: Sequence[dt.date]) -> dt.date:
    """The requested date, else today/next served date, else latest; dates must be sorted."""
    if requested is not None:
        return requested
    index = bisect.bisect_left(game_dates, today)
    if index < len(game_dates):
        return game_dates[index]
    return game_dates[-1] if game_dates else today


def adjacent_dates(date: dt.date, game_dates: Sequence[dt.date]) -> tuple[dt.date | None, dt.date | None]:
    """Nearest earlier/later served dates; game_dates must be sorted ascending."""
    before = bisect.bisect_left(game_dates, date)
    after = bisect.bisect_right(game_dates, date)
    return (game_dates[before - 1] if before else None, game_dates[after] if after < len(game_dates) else None)

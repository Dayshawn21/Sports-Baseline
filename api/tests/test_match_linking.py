import datetime as dt

import pytest

from app.repositories.matches import find_match_for_player


class _Result:
    def __init__(self, value: int | None) -> None:
        self._value = value

    def fetchone(self) -> tuple[int] | None:
        if self._value is None:
            return None
        return (self._value,)


class _Session:
    def __init__(self, value: int | None = 72900) -> None:
        self.value = value
        self.statement = ""
        self.params: dict[str, object] = {}

    async def execute(self, statement, params: dict[str, object]):
        self.statement = str(statement)
        self.params = params
        return _Result(self.value)


@pytest.mark.anyio
async def test_find_match_for_player_guards_exact_start_time_links():
    session = _Session()
    start_time = dt.datetime(2026, 8, 29, 1, 0, tzinfo=dt.timezone.utc)

    match_id = await find_match_for_player(
        session,
        player_id=42,
        match_date=dt.date(2026, 8, 29),
        start_time=start_time,
    )

    assert match_id == 72900
    assert "status NOT IN ('completed', 'cancelled')" in session.statement
    assert "ABS(EXTRACT(EPOCH FROM (start_utc - :start_time))) <= 12 * 3600" in session.statement
    assert "start_utc IS NULL" in session.statement
    assert session.params == {
        "pid": 42,
        "dt": dt.date(2026, 8, 29),
        "start_time": start_time,
    }

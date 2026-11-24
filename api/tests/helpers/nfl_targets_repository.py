"""Shared fixtures and builders, first written for `test_nfl_targets_repository.py`."""
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import RowMapping
from sqlalchemy.sql.elements import TextClause


KICKOFF = datetime(2024, 10, 6, 17, tzinfo=UTC)


class _Result:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self) -> list[RowMapping]:
        return cast(list[RowMapping], self.rows)


class _Session:
    def __init__(self, *responses: list[dict[str, object]]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(self, statement: TextClause, params: dict[str, object]) -> _Result:
        self.calls.append((" ".join(str(statement).split()), params))
        return _Result(self.responses.pop(0))


def _history(**overrides: object) -> dict[str, object]:
    return {
        "player_id": 7, "game_id": 40, "season": 2024, "week": 4,
        "start_utc": KICKOFF, "targets": 4,
    } | overrides

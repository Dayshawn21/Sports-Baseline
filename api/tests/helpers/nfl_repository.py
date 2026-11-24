"""Shared fixtures and builders, first written for `test_nfl_repository.py`."""

from sqlalchemy.sql.elements import TextClause


class _Result:
    def __init__(self, result_id: int = 0) -> None:
        self.result_id = result_id

    def mappings(self) -> list[dict[str, object]]:
        return []

    def fetchall(self) -> list[tuple[object, ...]]:
        return []

    def scalar_one(self) -> int:
        return self.result_id


class _RecordingSession:
    def __init__(self) -> None:
        self.statement = ""
        self.params: dict[str, object] = {}
        self.result_id = 0

    async def execute(
        self,
        statement: TextClause,
        params: dict[str, object] | None = None,
    ) -> _Result:
        self.statement = str(statement)
        self.params = params or {}
        return _Result(self.result_id)

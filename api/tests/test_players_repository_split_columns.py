from types import SimpleNamespace

from sqlalchemy.exc import ProgrammingError

from app.repositories.players import _missing_split_columns

SPLIT_SQL = "SELECT split_type, split_value FROM player_rolling_stats WHERE surface = $2"


class FakeDriverError(Exception):
    def __init__(self, sqlstate: str, message_primary: str) -> None:
        super().__init__(message_primary)
        self.sqlstate = sqlstate
        self.diag = SimpleNamespace(message_primary=message_primary)


def _error(sqlstate: str, message_primary: str) -> ProgrammingError:
    return ProgrammingError(SPLIT_SQL, {}, FakeDriverError(sqlstate, message_primary))


def test_missing_split_column_is_recognized() -> None:
    assert _missing_split_columns(_error("42703", 'column "split_type" does not exist'))
    assert _missing_split_columns(_error("42703", 'column "split_value" does not exist'))


def test_other_errors_are_not_swallowed_although_the_sql_names_split_type() -> None:
    assert not _missing_split_columns(
        _error("42P18", "could not determine data type of parameter $2")
    )


def test_other_undefined_columns_are_not_swallowed() -> None:
    assert not _missing_split_columns(_error("42703", 'column "dominance_ratio" does not exist'))

"""Every read of `sport_game_odds` names its feed, so a new provider never leaks into old readers."""
import ast
import re
from pathlib import Path

from app.core.odds_providers import ODDS_API_IO, PROVIDERS, THE_ODDS_API_US

APP = Path(__file__).resolve().parents[1] / "app"
READ = re.compile(r"\b(FROM|JOIN)\s+sport_game_odds\b")


def _sql_strings() -> list[tuple[str, str]]:
    found = []
    for path in APP.rglob("*.py"):
        if "migrations" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and READ.search(node.value):
                found.append((str(path.relative_to(APP)), node.value))
    return found


def test_the_guard_sees_every_known_reader() -> None:
    files = [path for path, _ in _sql_strings()]

    assert files.count(str(Path("repositories/nfl.py"))) == 8
    assert files.count(str(Path("repositories/nba.py"))) == 3
    assert files.count(str(Path("repositories/nhl.py"))) == 1


def test_every_reader_filters_to_a_named_provider() -> None:
    unfiltered = [path for path, sql in _sql_strings() if not re.search(r"\bprovider\s*(=|IN)", sql)]

    assert unfiltered == []


def test_pre_36_readers_stay_on_the_feed_item_28_was_written_against() -> None:
    historical_readers = {str(Path("repositories/nfl.py")), str(Path("repositories/nba.py"))}
    single_feed = [sql for path, sql in _sql_strings() if path in historical_readers and "provider IN" not in sql]

    assert len(single_feed) == 10
    assert all(f"provider = '{THE_ODDS_API_US}'" in sql for sql in single_feed)


def test_nhl_readers_stay_on_odds_api_io() -> None:
    readers = [sql for path, sql in _sql_strings() if path == str(Path("repositories/nhl.py"))]
    assert len(readers) == 1
    assert all(f"o.provider = '{ODDS_API_IO}'" in sql and "o.sport = 'nhl'" in sql for sql in readers)


def test_a_multi_feed_reader_names_only_known_providers() -> None:
    for _, sql in _sql_strings():
        if "provider IN" in sql:
            named = re.search(r"provider IN \(([^)]*)\)", sql).group(1)
            assert {name.strip(" '") for name in named.split(",")} <= set(PROVIDERS)

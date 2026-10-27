import datetime as dt
import re
from pathlib import Path

from app.core.ask_links import board_path, game_path, model_path, player_path, slate_path

WEB_SRC = Path(__file__).resolve().parents[2] / "web" / "src"


def _web_route_patterns() -> list[re.Pattern[str]]:
    """Every route the web registers: sport views from sportNav.ts, detail pages from sportPages.tsx."""
    nav = (WEB_SRC / "utils" / "sportNav.ts").read_text(encoding="utf-8")
    pages = (WEB_SRC / "routes" / "sportPages.tsx").read_text(encoding="utf-8")
    views = re.findall(r"(?:slate|props|model): '([^']+)'", nav)
    details = re.findall(r"path: '([^']+)'", pages)
    assert views and details, "route sources moved; update this test"
    return [re.compile("^" + re.sub(r":\w+", r"[^/]+", path) + "$") for path in views + details]


def _routed(path: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(pattern.match(path.split("?")[0]) for pattern in patterns)


def test_every_builder_targets_a_registered_web_route():
    patterns = _web_route_patterns()
    built = [
        slate_path("nba"), slate_path("nfl"), slate_path("tennis"),
        game_path("nba", 1), game_path("nfl", 2), game_path("tennis", 3),
        player_path("nfl", 4), player_path("tennis", 5),
        model_path("nba"), model_path("nfl"), model_path("tennis"),
        board_path("nba"), board_path("tennis"),
    ]
    assert [path for path in built if not _routed(path, patterns)] == []


def test_slate_paths_carry_the_parameters_each_page_reads():
    date = dt.date(2026, 10, 27)
    assert slate_path("nba", date=date) == "/nba?date=2026-10-27"
    assert slate_path("nfl", season=2026, week=8) == "/nfl?season=2026&week=8"
    assert slate_path("nfl", season=2026) == "/nfl"
    assert slate_path("tennis", date=date) == "/"


def test_tennis_games_are_match_pages():
    assert game_path("tennis", 42) == "/tennis/match/42"
    assert game_path("nba", 42) == "/nba/game/42"


def test_board_date_applies_to_nba_only():
    date = dt.date(2026, 10, 27)
    assert board_path("nba", date) == "/nba/board?date=2026-10-27"
    assert board_path("tennis", date) == "/tennis/board"

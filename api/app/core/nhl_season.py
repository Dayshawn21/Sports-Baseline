"""NHL season labels and web API game states."""
from datetime import date

_GAME_TYPES = {2: "REG", 3: "PST"}


def current_nhl_season(today: date) -> int:
    """Count the next season from August, including the summer offseason."""
    return today.year if today.month >= 8 else today.year - 1


def season_id(season: int) -> str:
    return f"{season}{season + 1}"


def game_type(nhl_game_type: int) -> str | None:
    return _GAME_TYPES.get(nhl_game_type)


def game_status(game_state: str, game_schedule_state: str) -> str:
    if "CNCL" in (game_state, game_schedule_state):
        return "canceled"
    if "PPD" in (game_state, game_schedule_state):
        return "postponed"
    if game_schedule_state == "OK" and game_state in ("OFF", "FINAL"):
        return "completed"
    return "scheduled"


def end_period(status: str, last_period_type: str | None) -> str | None:
    if status == "completed" and last_period_type in ("REG", "OT", "SO"):
        return last_period_type
    return None

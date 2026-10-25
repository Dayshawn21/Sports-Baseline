"""Free nflverse files, cached in analysis/data/. The only module that imports nfl_data_py."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SCHEDULE_COLUMNS = ["game_id", "season", "game_type", "week", "home_team", "away_team", "home_score", "away_score"]


def _download_schedules(seasons: list[int]) -> pd.DataFrame:
    # Deprecated upstream; swapping to nflreadpy or nflverse's games.csv only changes this function.
    import nfl_data_py

    return nfl_data_py.import_schedules(seasons)


def schedule_cache_path(seasons: Sequence[int], data_dir: Path = DATA_DIR) -> Path:
    return data_dir / f"nflverse-schedules-{min(seasons)}-{max(seasons)}.csv"


def load_schedules(seasons: Sequence[int], *, data_dir: Path = DATA_DIR, refresh: bool = False) -> pd.DataFrame:
    """Every game type (REG, WC, DIV, CON, SB) for the seasons; downloads once, then reads the cache."""
    wanted = sorted(set(seasons))
    if wanted != list(range(wanted[0], wanted[-1] + 1)):
        raise ValueError(f"seasons must be a continuous range: {wanted}")
    path = schedule_cache_path(wanted, data_dir)
    if path.is_file() and not refresh:
        return pd.read_csv(path)
    frame = _download_schedules(wanted)[SCHEDULE_COLUMNS]
    missing = set(wanted) - set(frame["season"])
    if missing:
        raise ValueError(f"nflverse returned no games for seasons {sorted(missing)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return frame

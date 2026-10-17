"""Freeze the current NBA week's predictions for every line not yet tipped off (20g3).

Runs straight after each PrizePicks NBA line snapshot (`nba-prop-lines.yml`);
the shared body is `app.ingest.prop_predictions`.

Run from api/: python -m app.ingest.nba_prop_predictions [--dry-run]
"""
from __future__ import annotations

from app.ingest.prop_predictions import main

if __name__ == "__main__":
    main("nba")

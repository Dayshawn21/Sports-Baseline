"""Freeze the current NHL week's predictions for every line not yet at puck drop (56c4).

Runs straight after each PrizePicks NHL line snapshot (`nhl-prop-lines.yml`);
the shared body is `app.ingest.prop_predictions`.

Run from api/: python -m app.ingest.nhl_prop_predictions [--dry-run]
"""
from __future__ import annotations

from app.ingest.prop_predictions import main

if __name__ == "__main__":
    main("nhl")

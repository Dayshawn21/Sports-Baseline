"""Freeze the current NFL slate's predictions for every line not yet kicked off (27i).

Runs straight after each PrizePicks NFL line snapshot (`nfl-prop-lines.yml`);
the shared body is `app.ingest.prop_predictions`.

Run from api/: python -m app.ingest.nfl_prop_predictions [--dry-run]
"""
from __future__ import annotations

from app.ingest.prop_predictions import main

if __name__ == "__main__":
    main("nfl")

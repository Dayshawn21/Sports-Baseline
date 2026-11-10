from pathlib import Path

from app.core.prop_projection import PRIZEPICKS_HARD_BLOCKS
from app.core.tennis_prop_check import EXCLUDED_FLAGS
from app.services.tennis import prop_sim


def test_every_hard_block_is_emitted_by_the_props_router():
    source = (Path(__file__).resolve().parents[1] / "app" / "routers" / "props.py").read_text(encoding="utf-8")
    assert {flag for flag in PRIZEPICKS_HARD_BLOCKS if f'"{flag}"' not in source} == set()


def test_the_simulation_skips_the_rows_enrich_blocks():
    assert prop_sim.PRIZEPICKS_HARD_BLOCKS is PRIZEPICKS_HARD_BLOCKS


def test_forward_check_exclusions_are_unchanged():
    assert EXCLUDED_FLAGS == {
        "match_finished", "match_link_invalid", "bo5_unsupported_stat", "unsupported_stat",
        "ungraded_stat", "missing_player", "missing_match",
    }

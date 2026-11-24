"""The one rule for surface versus all-surface stats (F-24): props, best picks,
prop sim and the Bankroll Builder all read it."""
from types import SimpleNamespace

from app.core.rolling_stats import SMALL_SAMPLE_MATCHES, pick_stats_for_player


def _stats(matches_count: int | None):
    return SimpleNamespace(matches_count=matches_count)


CLAY_THRESHOLD = _stats(SMALL_SAMPLE_MATCHES)
CLAY_SHORT = _stats(SMALL_SAMPLE_MATCHES - 1)
OVERALL = _stats(60)


def test_the_threshold_is_ten_matches():
    assert SMALL_SAMPLE_MATCHES == 10


def test_a_surface_sample_at_the_threshold_is_used():
    stats = {(1, "Clay"): CLAY_THRESHOLD, (1, None): OVERALL}
    assert pick_stats_for_player(1, "Clay", stats) is CLAY_THRESHOLD


def test_a_surface_sample_below_the_threshold_falls_back_to_all_surface():
    stats = {(1, "Clay"): CLAY_SHORT, (1, None): OVERALL}
    assert pick_stats_for_player(1, "Clay", stats) is OVERALL


def test_a_surface_row_without_a_count_falls_back():
    stats = {(1, "Clay"): _stats(None), (1, None): OVERALL}
    assert pick_stats_for_player(1, "Clay", stats) is OVERALL


def test_a_missing_surface_row_falls_back():
    assert pick_stats_for_player(1, "Grass", {(1, None): OVERALL}) is OVERALL


def test_a_short_surface_sample_with_no_fallback_returns_none():
    assert pick_stats_for_player(1, "Clay", {(1, "Clay"): CLAY_SHORT}) is None


def test_no_player_returns_none():
    assert pick_stats_for_player(None, "Clay", {(1, None): OVERALL}) is None

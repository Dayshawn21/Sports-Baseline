import asyncio
from datetime import date

from app.ingest import player_stats
from app.repositories import player_match_stats


def _make_row(
    match_date: str,
    *,
    surface: str = "Hard",
    wl: str = "W",
    opp_rank: str = "25",
) -> list:
    row = [""] * 39
    row[player_stats.I_DATE] = match_date
    row[player_stats.I_SURFACE] = surface
    row[player_stats.I_WL] = wl
    row[player_stats.I_ORANK] = opp_rank
    row[player_stats.I_ACES] = "5"
    row[player_stats.I_DFS] = "2"
    row[player_stats.I_PTS] = "60"
    row[player_stats.I_FIRSTS] = "40"
    row[player_stats.I_FWON] = "30"
    row[player_stats.I_SWON] = "10"
    row[player_stats.I_GAMES] = "10"
    row[player_stats.I_SAVED] = "3"
    row[player_stats.I_CHANCES] = "4"
    row[player_stats.I_OPTS] = "60"
    row[player_stats.I_OFWON] = "25"
    row[player_stats.I_OSWON] = "10"
    row[player_stats.I_OGAMES] = "10"
    row[player_stats.I_OSAVED] = "2"
    row[player_stats.I_OCHANCES] = "4"
    return row


def test_aggregate_baseline_and_surface_filters():
    rows = [
        _make_row("20260320", surface="Hard", wl="W", opp_rank="8"),
        _make_row("20260318", surface="Hard", wl="L", opp_rank="15"),
        _make_row("20260310", surface="Hard", wl="W", opp_rank="42"),
        _make_row("20260215", surface="Clay", wl="W", opp_rank="70"),
    ]

    all_stats = player_stats._aggregate(rows, "20250101")
    hard_stats = player_stats._aggregate(rows, "20250101", surface="Hard")

    assert all_stats is not None
    assert all_stats["matches_count"] == 4
    assert all_stats["win_rate"] == 0.75

    assert hard_stats is not None
    assert hard_stats["matches_count"] == 3
    assert hard_stats["win_rate"] == 0.6667
    assert hard_stats["break_points_created_per_return_game"] == 0.4
    assert hard_stats["allowed_break_points_per_service_game"] == 0.4


def test_aggregate_opp_rank_buckets():
    rows = [
        _make_row("20260320", opp_rank="3"),
        _make_row("20260318", opp_rank="6"),
        _make_row("20260310", opp_rank="9"),
        _make_row("20260301", opp_rank="25"),
        _make_row("20260215", opp_rank="60"),
        _make_row("20260210", opp_rank="75"),
        _make_row("20260205", opp_rank="91"),
    ]

    top10_stats = player_stats._aggregate(rows, "20250101", opp_rank_bucket="top10")
    plus51_stats = player_stats._aggregate(rows, "20250101", opp_rank_bucket="plus51")
    top5_stats = player_stats._aggregate(rows, "20250101", opp_rank_bucket="top5")

    assert top10_stats is not None
    assert top10_stats["matches_count"] == 3

    assert plus51_stats is not None
    assert plus51_stats["matches_count"] == 3

    assert top5_stats is None


def test_season_cutoff_uses_current_year_start():
    assert player_stats._season_cutoff(player_stats.date(2026, 4, 1)) == "20260101"


def test_filter_players_for_refresh_keeps_all_when_skip_disabled():
    players = [
        (1, "Fresh Player", "ATP"),
        (2, "Stale Player", "WTA"),
    ]

    filtered = player_stats._filter_players_for_refresh(
        players,
        {1},
        skip_computed_today=False,
    )

    assert filtered == players


def test_filter_players_for_refresh_skips_same_day_baseline_players():
    players = [
        (1, "Fresh Player", "ATP"),
        (2, "Stale Player", "WTA"),
        (3, "No Stats Player", "ATP"),
    ]

    filtered = player_stats._filter_players_for_refresh(
        players,
        {1},
        skip_computed_today=True,
    )

    assert filtered == [
        (2, "Stale Player", "WTA"),
        (3, "No Stats Player", "ATP"),
    ]


def test_filter_players_for_refresh_ignores_non_baseline_rows_when_no_fresh_ids():
    players = [
        (1, "Surface Only Player", "ATP"),
        (2, "Contextual Only Player", "ATP"),
    ]

    filtered = player_stats._filter_players_for_refresh(
        players,
        set(),
        skip_computed_today=True,
    )

    assert filtered == players


def test_persist_writes_opp_rank_rows_regardless_of_tour(monkeypatch):
    written: list[str] = []

    async def fake_upsert_stat_row(db, *, split_type, split_value, surface, **_kwargs):
        if split_type == "opp_rank" and surface is None:
            written.append(split_value)

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(player_stats, "_upsert_baseline_rows", noop)
    monkeypatch.setattr(player_stats, "_upsert_stat_row", fake_upsert_stat_row)
    monkeypatch.setattr(player_match_stats, "upsert_player_match_stats", noop)

    today = date(2026, 10, 1)
    rows = [_make_row(f"2026090{day}", opp_rank="12") for day in range(1, 4)]
    asyncio.run(player_stats._persist_player_stats(None, 2011, rows, today))

    assert written == ["top20", "top50"]

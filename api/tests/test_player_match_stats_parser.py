from datetime import date

from app.ingest.player_stats import _parse_player_match_stats, _resolve_backfill_active_options


def _row() -> list:
    row = [None] * 39
    row[0] = "20260910"
    row[2] = "Hard"
    row[4] = "W"
    row[21] = 8
    row[22] = 3
    row[27] = 11
    row[28] = 4
    row[29] = 6
    row[37] = 1
    row[38] = 5
    return row


def test_parse_player_match_stats_keeps_exact_counts_and_break_conversion():
    stats = _parse_player_match_stats(17, [_row()], "20250921")

    assert len(stats) == 1
    stat = stats[0]
    assert stat.player_id == 17
    assert stat.match_date == date(2026, 9, 10)
    assert stat.surface == "Hard"
    assert stat.result == "W"
    assert stat.aces == 8
    assert stat.double_faults == 3
    assert stat.break_points_faced == 6
    assert stat.break_points_saved == 4
    assert stat.break_chances_created == 5
    assert stat.break_points_converted == 4


def test_parse_player_match_stats_excludes_old_or_incomplete_rows():
    old = _row()
    old[0] = "20240910"
    incomplete = _row()[:20]

    assert _parse_player_match_stats(17, [old, incomplete], "20250921") == []


def _with_join_key(tournament, result, round_, score, opponent) -> list:
    row = _row()
    row[1], row[4], row[8], row[9], row[11] = tournament, result, round_, score, opponent
    return row


def test_join_key_fields_from_a_classic_page_row():
    (stat,) = _parse_player_match_stats(
        17, [_with_join_key("Wimbledon", "W", "SF", "6-4 6-4 6-4", "Novak Djokovic")], "20250921",
    )
    assert (stat.tournament, stat.round, stat.score, stat.opponent_name) == (
        "Wimbledon", "SF", "6-4 6-4 6-4", "Novak Djokovic",
    )


def test_join_key_keeps_the_winner_first_score_and_tie_breaks_on_a_loss():
    # TennisAbstract scores read from the winner's side even on the player's own losses.
    (stat,) = _parse_player_match_stats(
        17, [_with_join_key("US Open", "L", "R16", "7-6(3) 6-3", "Qinwen Zheng")], "20250921",
    )
    assert stat.result == "L" and stat.score == "7-6(3) 6-3" and stat.opponent_name == "Qinwen Zheng"


def test_blank_join_key_fields_become_none():
    (stat,) = _parse_player_match_stats(17, [_with_join_key("", "W", " ", None, "")], "20250921")
    assert (stat.tournament, stat.round, stat.score, stat.opponent_name) == (None, None, None, None)


def test_the_upsert_writes_and_refreshes_the_join_key():
    import asyncio
    from typing import cast

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.repositories.player_match_stats import upsert_player_match_stats

    class _Session:
        statement = ""
        params: list = []

        async def execute(self, statement, params=None):
            self.statement, self.params = " ".join(str(statement).split()), params

    session = _Session()
    stats = _parse_player_match_stats(
        17, [_with_join_key("Wimbledon", "W", "F", "6-4 6-4", "Alexander Zverev")], "20250921",
    )
    asyncio.run(upsert_player_match_stats(cast(AsyncSession, session), stats))
    for column in ("opponent_name", "round", "tournament"):
        assert f"{column} = EXCLUDED.{column}" in session.statement
        assert f":{column}" in session.statement
    assert session.params[0]["opponent_name"] == "Alexander Zverev"
    assert session.params[0]["source"] == "tennisabstract"


def test_the_upsert_binds_an_explicit_source_for_every_row():
    import asyncio
    from typing import cast

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.repositories.player_match_stats import upsert_player_match_stats

    class _Session:
        statement = ""
        params: list[dict] = []

        async def execute(self, statement, params=None):
            self.statement, self.params = " ".join(str(statement).split()), params

    session = _Session()
    stats = _parse_player_match_stats(17, [_row(), _row()], "20250921")
    asyncio.run(upsert_player_match_stats(cast(AsyncSession, session), stats, source="tennismylife"))
    assert ":player_id, :source, :source_match_key" in session.statement
    assert [row["source"] for row in session.params] == ["tennismylife", "tennismylife"]


def test_the_upsert_never_blanks_a_published_score_or_stat():
    # One row now lives through placeholder, score-only and full stats.
    import asyncio
    from typing import cast

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.repositories.player_match_stats import upsert_player_match_stats

    class _Session:
        statement = ""

        async def execute(self, statement, params=None):
            self.statement = " ".join(str(statement).split())

    session = _Session()
    stats = _parse_player_match_stats(17, [_with_join_key("Wimbledon", "W", "F", "6-4 6-4", "Alexander Zverev")], "20250921")
    asyncio.run(upsert_player_match_stats(cast(AsyncSession, session), stats))
    for column in ("result", "score", "aces", "double_faults", "service_games", "break_points_faced",
                   "break_points_saved", "break_chances_created", "break_points_converted", "surface"):
        assert f"{column} = COALESCE(EXCLUDED.{column}, player_match_stats.{column})" in session.statement


def test_active_backfill_forces_slate_refresh_and_keeps_existing_window():
    assert _resolve_backfill_active_options(False, 5, 3, True, True) == (True, 0, 3, False)
    assert _resolve_backfill_active_options(False, 5, 0, True, True) == (True, 0, 1, False)


def _stage(result, score, aces, tournament="WTA Adana 125", round_="R32", opponent="Vendula Valdmannova") -> list:
    row = _with_join_key(tournament, result, round_, score, opponent)
    row[0] = "20260928"
    row[21] = aces
    return row


def test_one_match_keeps_one_key_through_every_stage_tennisabstract_publishes():
    placeholder, score_only, full = _stage("", None, None), _stage("W", "6-4 6-3", None), _stage("W", "6-4 6-3", 1)
    keys = {s.source_match_key for s in _parse_player_match_stats(17, [placeholder, score_only, full], "20250921")}
    assert len(keys) == 1


def test_round_robin_opponents_in_one_round_keep_two_keys():
    first = _stage("W", "6-3 6-3", 4, tournament="ATP Finals", round_="RR", opponent="Jannik Sinner")
    second = _stage("L", "6-4 6-4", 2, tournament="ATP Finals", round_="RR", opponent="Carlos Alcaraz")
    assert len({s.source_match_key for s in _parse_player_match_stats(17, [first, second], "20250921")}) == 2


def test_case_and_spacing_do_not_change_the_key():
    from app.ingest.player_stats import box_score_key

    assert box_score_key("20260928", "WTA Adana 125", "R32", "Vendula Valdmannova", []) == box_score_key(
        "20260928", " wta adana 125", "r32 ", "VENDULA VALDMANNOVA", ["different", "raw"],
    )


def test_a_missing_key_part_falls_back_to_the_raw_row_hash():
    from app.ingest.player_stats import box_score_key

    row_a, row_b = _stage("W", "6-4", 1, opponent=""), _stage("W", "6-4", 2, opponent="")
    assert box_score_key("20260928", "WTA Adana 125", "R32", None, row_a) != box_score_key(
        "20260928", "WTA Adana 125", "R32", None, row_b,
    )


def test_the_v2_key_matches_the_value_migration_0038_computes_in_sql():
    # Postgres: encode(sha256(convert_to('v2|20260928|wta adana 125|r32|vendula valdmannova', 'UTF8')), 'hex')
    from app.ingest.player_stats import box_score_key

    assert box_score_key("20260928", "WTA Adana 125", "R32", "Vendula Valdmannova", []) == (
        "20a9bf77be87159f1f126efd1e2f1947ba6f96bdaf0d2a2df0ab2ccbdf005dc3"
    )

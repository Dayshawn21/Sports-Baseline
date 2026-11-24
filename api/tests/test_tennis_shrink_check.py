import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtest import tennis_shrink_check as check
from app.repositories import predictions as repo
from app.repositories.predictions import MatchResult, ShadowCheckRow

START = date(2026, 12, 1)
WTA = "ensemble-v3+lgbm-v6"
CHAL = "ensemble-v3+lgbm-none"
_ids = iter(range(1, 100_000))


def _row(day: int, tour: str = "WTA", status: str = "completed", version: str = WTA,
         ensemble: float = 0.66, market: float = 0.60, shadow: float | None = 0.63) -> ShadowCheckRow:
    start = datetime.combine(START + timedelta(days=day), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=14)
    return ShadowCheckRow(next(_ids), tour, start, status, version, ensemble, market, shadow)


@pytest.fixture
def small_floors(monkeypatch):
    monkeypatch.setattr(check, "MIN_AFFECTED", 3)
    monkeypatch.setattr(check, "MIN_DAYS", 2)


LATE = START + timedelta(days=60)


def _state(rows, as_of=LATE, name="ATP+WTA", resolve=None):
    return check.slice_state(rows, name, START, as_of, resolve or check.count_resolver(as_of))


def test_pins_and_constants():
    assert check.PINNED_VERSIONS == {"ATP+WTA": WTA, "CHALLENGER": CHAL}
    assert check.NEVER_RESOLVED_DAYS == 14
    assert check.SHADOW_SUFFIX == "+shrink-v1"


def test_start_is_the_first_full_utc_day_after_the_first_shadow():
    first = datetime(2026, 11, 30, 23, 30, tzinfo=timezone(timedelta(hours=-6)))
    assert check.check_start(first) == date(2026, 12, 2)


def test_maturity_needs_the_day_to_close_plus_three_days():
    assert not check.is_mature(START, START + timedelta(days=3))
    assert check.is_mature(START, START + timedelta(days=4))


def test_lock_includes_the_whole_first_day_reaching_both_floors(small_floors):
    rows = [_row(0), _row(1), _row(1), _row(2), _row(3)]
    state = _state(rows)
    assert state.locked_on == START + timedelta(days=1)
    assert len(state.included) == 3 and state.days == 2
    assert state.status == "floors met"


def test_the_day_floor_holds_even_with_enough_matches(small_floors):
    state = _state([_row(0), _row(0), _row(0), _row(0)])
    assert state.locked_on is None and state.status == "accruing"


def test_unaffected_and_unshadowed_rows_never_enter_the_sample(small_floors):
    rows = [_row(0, ensemble=0.62), _row(0, shadow=None), _row(1), _row(2)]
    state = _state(rows)
    assert state.affected == 2 and state.locked_on is None


def test_an_unresolved_earlier_match_blocks_the_lock(small_floors):
    rows = [_row(0, status="scheduled"), _row(1), _row(2), _row(3)]
    as_of = START + timedelta(days=10)
    state = _state(rows, as_of=as_of)
    assert state.locked_on is None
    assert (state.stopped_on, state.stop_reason) == (START, "unresolved match")


def test_a_match_unresolved_for_fourteen_days_is_dropped_and_counted(small_floors):
    rows = [_row(0, status="scheduled"), _row(1), _row(2), _row(3)]
    state = _state(rows, as_of=START + timedelta(days=14))
    assert state.never_resolved == 1
    assert state.locked_on == START + timedelta(days=3)


def test_an_immature_day_stops_the_walk(small_floors):
    rows = [_row(0), _row(1), _row(5)]
    state = _state(rows, as_of=START + timedelta(days=6))
    assert (state.stopped_on, state.stop_reason) == (START + timedelta(days=5), "not yet mature")


def test_cancelled_matches_are_excluded(small_floors):
    state = _state([_row(0, status="cancelled"), _row(0), _row(1)])
    assert state.excluded == 1 and len(state.included) == 2


def test_coverage_below_98_percent_blocks_the_slice(small_floors):
    rows = [_row(0), _row(1), _row(2)] + [_row(0, ensemble=0.61, shadow=None)]
    state = _state(rows)
    assert state.coverage == pytest.approx(0.75)
    assert state.status == "blocked: coverage"


def test_a_served_version_change_interrupts_the_slice(small_floors):
    rows = [_row(0), _row(1), _row(2, version="ensemble-v4+lgbm-v6"), _row(3), _row(4)]
    state = _state(rows)
    assert state.interrupted_on == START + timedelta(days=2)
    assert state.locked_on is None and state.status == "accruing (interrupted)"


def test_challenger_uses_its_own_pin_and_is_never_pooled(small_floors):
    rows = [_row(0, tour="CHALLENGER", version=CHAL), _row(1, tour="CHALLENGER", version=CHAL),
            _row(2, tour="CHALLENGER", version=CHAL), _row(0)]
    assert _state(rows, name="CHALLENGER").locked_on == START + timedelta(days=2)
    assert len(_state(rows).included) == 1


def test_rows_before_the_start_are_ignored(small_floors):
    state = _state([_row(-1), _row(0)])
    assert len(state.included) == 1


def test_score_resolver_excludes_retirements_and_waits_for_a_winner():
    as_of = START + timedelta(days=5)
    done, retired, no_winner = _row(0), _row(0), _row(0)
    resolve = check.score_resolver(as_of, {
        done.match_id: MatchResult(True, True),
        retired.match_id: MatchResult(False, False),
        no_winner.match_id: MatchResult(None, False),
    })
    assert [resolve(r) for r in (done, retired, no_winner)] == ["included", "excluded", "unresolved"]


def test_score_candidates_are_affected_shadowed_and_mature():
    keep, unaffected, young = _row(0), _row(0, ensemble=0.61), _row(10)
    ids = check.score_candidates([keep, unaffected, young], "ATP+WTA", START, START + timedelta(days=6))
    assert ids == [keep.match_id]


def test_score_lines_print_the_verdict(small_floors):
    rows = [_row(0), _row(1), _row(1, ensemble=0.54, market=0.60, shadow=0.57)]
    results = {r.match_id: MatchResult(True, True) for r in rows}
    state = _state(rows, resolve=check.score_resolver(LATE, results))
    text = "\n".join(check.score_lines(state, results))
    assert "ATP+WTA VERDICT" in text and "Shadow minus served" in text
    assert "-> accruing" in text  # the frozen 400 floor in core still applies to the verdict


def test_count_lines_say_counts_only(small_floors):
    text = "\n".join(check.count_lines([_state([_row(0)])], LATE))
    assert "COUNTS ONLY" in text and "No outcome or loss is read here." in text


class _Rows:
    def __init__(self, rows=None, scalar=None):
        self._rows, self._scalar = rows or [], scalar

    def fetchall(self):
        return self._rows

    def scalar_one(self):
        return self._scalar


class _Session:
    def __init__(self, result: _Rows):
        self.result, self.statement, self.params = result, "", {}

    async def execute(self, statement, params=None):
        self.statement, self.params = " ".join(str(statement).split()), params or {}
        return self.result


def test_count_loader_selects_no_result_column():
    session = _Session(_Rows())
    asyncio.run(repo.get_shadow_check_rows(cast(AsyncSession, session), datetime(2026, 12, 1, tzinfo=timezone.utc),
                                           "+shrink-v1"))
    select = session.statement.split(" FROM matches m")[0]
    for column in ("winner", "score", "close", "p1_won"):
        assert column not in select
    assert "generated_at < m.start_utc" in session.statement
    assert "s.model_version = p.model_version || :suffix" in session.statement


def test_result_loader_maps_winner_and_completed_score():
    session = _Session(_Rows([(1, "6-3 6-4", 3, 10, 10), (2, "6-3 2-1", 3, 11, 10), (3, None, 3, None, 10)]))
    results = asyncio.run(repo.get_match_results(cast(AsyncSession, session), [1, 2, 3]))
    assert results == {1: MatchResult(True, True), 2: MatchResult(False, False), 3: MatchResult(None, False)}


def test_count_mode_never_loads_results(monkeypatch):
    calls: list[str] = []

    class _Db:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    async def first(db, suffix):
        return datetime(2026, 11, 30, tzinfo=timezone.utc)

    async def rows(db, since, suffix):
        return [_row(1)]

    async def results(db, ids):
        calls.append("results")
        return {}

    import app.db.pool as pool
    monkeypatch.setattr(pool, "SessionLocal", lambda: _Db())
    monkeypatch.setattr(repo, "get_first_shadow_at", first)
    monkeypatch.setattr(repo, "get_shadow_check_rows", rows)
    monkeypatch.setattr(repo, "get_match_results", results)
    text = asyncio.run(check._load(None, LATE))
    assert "COUNTS ONLY" in text and calls == []
    refused = asyncio.run(check._load("ATP+WTA", LATE))
    assert "Refused" in refused and calls == []

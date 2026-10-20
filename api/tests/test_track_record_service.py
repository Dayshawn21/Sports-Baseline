from datetime import datetime, timedelta, timezone
from math import log

import pytest

from app.repositories.predictions import GradedPrediction
from app.services.tennis.track_record import VersionCount, build_prediction_grading, version_counts

MODEL = "ensemble-v1+lgbm-v6"
GRADED_AT = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
START = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)


def _row(i: int, tour: str = "ATP", *, p1_won: bool = True, market: float | None = 0.6,
         ensemble: float | None = 0.65, close: float | None = None, version: str = MODEL,
         completed: bool = True, ml: float | None = 0.62, elo: float | None = 0.6) -> GradedPrediction:
    start = START + timedelta(hours=i)
    return GradedPrediction(
        match_id=i, tour=tour, start_utc=start, generated_at=start - timedelta(hours=2),
        model_version=version, p1_won=p1_won, completed_score=completed,
        elo_prob=elo, ml_prob=ml, market_prob=market, ensemble_prob=ensemble,
        market_book="draftkings", closing_market_prob=close,
    )


def _group(grading, name):
    return next(g for g in grading.groups if g.group == name)


def test_counts_follow_the_report_exclusions():
    rows = [_row(1), _row(2, version="ensemble-v1+lgbm-v5"), _row(3, completed=False),
            _row(4, market=None), _row(5, close=0.62)]

    counts = build_prediction_grading(rows, MODEL, GRADED_AT).counts

    assert (counts.settled, counts.other_versions, counts.incomplete, counts.graded) == (5, 1, 1, 3)
    assert (counts.with_market, counts.with_close) == (2, 1)


def test_groups_use_the_common_subset_with_the_market_first():
    rows = [_row(1), _row(2, p1_won=False), _row(3, ml=None), _row(4, tour="WTA")]

    grading = build_prediction_grading(rows, MODEL, GRADED_AT)
    atp = _group(grading, "ATP")

    assert atp.n == 2
    assert [c.name for c in atp.components] == ["market", "ensemble", "elo", "ml"]
    assert atp.components[0].vs_market is None
    assert _group(grading, "ATP+WTA").n == 3
    assert _group(grading, "CHALLENGER").n == 0
    assert _group(grading, "CHALLENGER").components == []


def test_vs_market_carries_the_paired_difference_and_its_signal():
    rows = [_row(i, ensemble=0.9, market=0.6) for i in range(40)]

    ensemble = _group(build_prediction_grading(rows, MODEL, GRADED_AT), "ATP").components[1]

    assert ensemble.vs_market is not None
    assert ensemble.vs_market.mean < 0
    # Identical rows leave no spread, so there is no error bar to clear.
    assert ensemble.vs_market.standard_error == pytest.approx(0.0)
    assert ensemble.vs_market.signal == "positive"


def test_a_losing_component_stays_neutral():
    rows = [_row(i, ensemble=0.3, market=0.6) for i in range(40)]

    ensemble = _group(build_prediction_grading(rows, MODEL, GRADED_AT), "ATP").components[1]

    assert ensemble.vs_market.mean > 0
    assert ensemble.vs_market.signal == "neutral"


def test_clv_lines_split_away_from_toward():
    rows = [
        _row(1, ensemble=0.70, market=0.60, close=0.62),  # toward
        _row(2, ensemble=0.70, market=0.60, close=0.58),  # away
        _row(3, ensemble=0.70, market=0.60, close=0.60),  # unmoved
        _row(4, ensemble=0.61, market=0.60, close=0.65),  # toward, gap under 3 pts
    ]

    clv = build_prediction_grading(rows, MODEL, GRADED_AT).clv
    everything = next(c for c in clv if c.group == "all" and c.min_gap == 0.0)
    wide = next(c for c in clv if c.group == "all" and c.min_gap > 0)

    assert (everything.eligible, everything.moved, everything.toward, everything.away) == (4, 3, 2, 1)
    assert (wide.eligible, wide.toward, wide.away) == (3, 1, 1)
    assert {c.group for c in clv} == {"all", "ATP", "WTA", "ATP+WTA", "CHALLENGER"}


def test_calibration_is_pooled_atp_and_wta_only():
    rows = [_row(1), _row(2, tour="WTA"), _row(3, tour="CHALLENGER")]

    calibration = build_prediction_grading(rows, MODEL, GRADED_AT).calibration

    assert [s.source for s in calibration] == ["ensemble", "market", "ml"]
    assert sum(b.n for b in calibration[0].bins) == 2


@pytest.mark.parametrize("elo,ml,ensemble", [(0.6, None, 0.65), (None, None, 0.6), (0.99, None, 0.6)])
def test_ensemble_market_pair_does_not_require_ml_or_usable_elo(elo, ml, ensemble):
    grading = build_prediction_grading(
        [_row(1, tour="CHALLENGER", elo=elo, ml=ml, ensemble=ensemble)], MODEL, GRADED_AT,
    )
    pair = next(g for g in grading.ensemble_market_groups if g.group == "CHALLENGER")

    assert pair.n == 1
    assert [c.name for c in pair.components] == ["market", "ensemble"]
    market, candidate = pair.components
    assert market.log_loss == pytest.approx(-log(0.6))
    assert market.brier == pytest.approx(0.4 ** 2)
    assert market.vs_market is None
    assert candidate.log_loss == pytest.approx(-log(ensemble))
    assert candidate.brier == pytest.approx((1 - ensemble) ** 2)
    assert candidate.vs_market.mean == pytest.approx(log(0.6 / ensemble))
    assert candidate.vs_market.standard_error is None
    assert candidate.vs_market.signal == "neutral"
    assert _group(grading, "CHALLENGER").n == 0
    assert all(g.n == 0 for g in grading.ensemble_market_groups if g.group != "CHALLENGER")
    assert all(not s.bins for s in grading.calibration)


def test_ensemble_market_pair_uses_its_own_sample_and_paired_error():
    rows = [_row(1, ensemble=0.8), _row(2, ensemble=0.3, p1_won=False, ml=None)]
    grading = build_prediction_grading(rows, MODEL, GRADED_AT)
    pair = next(g for g in grading.ensemble_market_groups if g.group == "ATP")
    candidate = pair.components[1]
    differences = [log(0.6 / 0.8), log(0.4 / 0.7)]

    assert pair.n == 2
    assert pair.components[0].log_loss == pytest.approx((-log(0.6) - log(0.4)) / 2)
    assert candidate.log_loss == pytest.approx((-log(0.8) - log(0.7)) / 2)
    assert candidate.brier == pytest.approx((0.2 ** 2 + 0.3 ** 2) / 2)
    assert candidate.vs_market.mean == pytest.approx(sum(differences) / 2)
    assert candidate.vs_market.standard_error == pytest.approx(abs(differences[0] - differences[1]) / 2)
    assert candidate.vs_market.signal == "positive"
    assert _group(grading, "ATP").n == 1
    assert sum(b.n for b in grading.calibration[0].bins) == 1


def test_ensemble_market_pair_excludes_missing_probabilities_incomplete_and_other_versions():
    rows = [
        _row(1, ml=None), _row(2, market=None), _row(3, ensemble=None),
        _row(4, completed=False), _row(5, version="ensemble-v3+lgbm-none"),
        _row(6, tour="WTA", elo=None), _row(7, tour="CHALLENGER", ml=None),
    ]
    grading = build_prediction_grading(rows, MODEL, GRADED_AT)

    assert {g.group: g.n for g in grading.ensemble_market_groups} == {
        "ATP": 1, "WTA": 1, "ATP+WTA": 2, "CHALLENGER": 1,
    }
    assert all(g.n == 0 for g in grading.groups)
    assert all(not s.bins for s in grading.calibration)


def test_versions_lead_with_the_served_one_then_the_newest_predicted():
    rows = [_row(1, version="ensemble-v1+lgbm-v5"), _row(2), _row(3), _row(4, version="ensemble-v2+lgbm-v6")]

    versions = version_counts(rows, "ensemble-v3+lgbm-v6")

    assert versions == [
        VersionCount("ensemble-v3+lgbm-v6", 0, True),
        VersionCount("ensemble-v2+lgbm-v6", 1, False),
        VersionCount(MODEL, 2, False),
        VersionCount("ensemble-v1+lgbm-v5", 1, False),
    ]


def test_a_served_version_with_rows_is_listed_once():
    versions = version_counts([_row(1), _row(2, version="ensemble-v1+lgbm-v5")], MODEL)

    assert [(v.model_version, v.settled, v.served) for v in versions] == [
        (MODEL, 1, True), ("ensemble-v1+lgbm-v5", 1, False),
    ]


def test_no_rows_gives_empty_sections():
    grading = build_prediction_grading([], MODEL, GRADED_AT)

    assert grading.counts.graded == 0
    assert all(g.n == 0 for g in grading.groups)
    assert all(g.n == 0 and g.components == [] for g in grading.ensemble_market_groups)
    assert all(s.bins == [] for s in grading.calibration)
    assert grading.graded_at == GRADED_AT


from app.repositories.props import PrizePicksLineRow  # noqa: E402
from app.services.tennis.track_record import build_line_settlement  # noqa: E402


def _line(i: int, line: float, odds_type: str = "standard", *, stat: str = "Total Games",
          live: bool = False, score: str = "6-4 6-3") -> PrizePicksLineRow:
    return PrizePicksLineRow(
        prop_id=i, player_id=i, match_id=1000 + i, tour="ATP", stat_type=stat, odds_type=odds_type,
        line=line, fetched_at=START, start_utc=START + timedelta(hours=1), player_is_p1=True,
        score=score, best_of=3, is_live=live, is_promo=False,
    )


def _settlement_row(settlement, stat, odds_type):
    return next(r for r in settlement.rows if r.stat == stat and r.odds_type == odds_type)


def test_over_rate_excludes_pushes():
    rows = [_line(1, 18.5), _line(2, 18.5), _line(3, 20.5), _line(4, 19.0)]

    row = _settlement_row(build_line_settlement(rows, {}, GRADED_AT), "total_games", "standard")

    assert row.settled == 4
    assert (row.over_share, row.under_share, row.push_share) == (0.5, 0.25, 0.25)
    assert row.over_rate == pytest.approx(2 / 3)
    assert row.standard_error == pytest.approx((2 / 3 * 1 / 3 / 3) ** 0.5)
    assert row.break_even == pytest.approx(0.5774, abs=1e-4)


def test_goblin_and_demon_get_no_error_bar_or_color():
    rows = [_line(i, 25.5, "goblin") for i in range(50)] + [_line(100 + i, 10.5, "demon") for i in range(50)]

    settlement = build_line_settlement(rows, {}, GRADED_AT)

    for odds_type in ("goblin", "demon"):
        row = _settlement_row(settlement, "total_games", odds_type)
        assert row.standard_error is None
        assert row.signal == "neutral"


def test_standard_far_below_break_even_is_negative():
    rows = [_line(i, 18.5) for i in range(20)] + [_line(100 + i, 20.5) for i in range(80)]

    row = _settlement_row(build_line_settlement(rows, {}, GRADED_AT), "total_games", "standard")

    assert row.over_rate == pytest.approx(0.2)
    assert row.signal == "negative"


def test_line_exclusions_are_totalled():
    rows = [_line(1, 18.5), _line(2, 18.5, live=True), _line(3, 18.5, score="6-4 3-1"),
            _line(4, 5.5, stat="Aces")]

    settlement = build_line_settlement(rows, {}, GRADED_AT)

    ex = settlement.excluded
    assert (ex.live, ex.promo, ex.incomplete_score) == (1, 0, 1)
    assert ex.unjoined == 1  # aces need a box score and none joined
    assert [(r.stat, r.odds_type) for r in settlement.rows] == [("total_games", "standard")]


def test_a_unanimous_rate_gets_no_error_bar():
    row = _settlement_row(build_line_settlement([_line(1, 18.5), _line(2, 18.5)], {}, GRADED_AT),
                          "total_games", "standard")

    assert row.over_rate == 1.0
    assert row.standard_error is None
    assert row.signal == "neutral"


from app.repositories.prop_snapshots import GradedPropSnapshot  # noqa: E402
from app.services.tennis.track_record import build_tier_grading  # noqa: E402

AS_OF = GRADED_AT.date()
OLD_DAY = datetime(2026, 9, 1, 13, 30, tzinfo=timezone.utc)
FRESH_DAY = datetime(2026, 9, 28, 13, 30, tzinfo=timezone.utc)


def _snap(i: int, *, confidence: str = "LEAN", recommendation: str | None = "UNDER", line: float = 19.5,
          odds_type: str = "standard", snapshot_at: datetime = OLD_DAY, score: str = "6-4 6-3") -> GradedPropSnapshot:
    return GradedPropSnapshot(
        snapshot_id=i, player_id=i, match_id=2000 + i, tour="ATP", stat_type="Total Games", odds_type=odds_type,
        line=line, recommendation=recommendation, confidence=confidence, hit_probability=0.6,
        player_is_p1=True, score=score, best_of=3, snapshot_at=snapshot_at,
    )


def _tier(grading, name):
    return next(t for t in grading.tiers if t.tier == name)


def test_tiers_grade_standard_lines_only_and_count_pushes_apart():
    rows = [_snap(1), _snap(2, recommendation="OVER"), _snap(3, line=19.0),
            _snap(4, odds_type="goblin"), _snap(5, confidence="PASS", recommendation=None),
            _snap(6, score="6-4 3-1")]

    grading = build_tier_grading(rows, {}, AS_OF, GRADED_AT)
    lean = _tier(grading, "LEAN")

    assert (lean.decided, lean.hits, lean.pushes) == (2, 1, 1)
    assert lean.hit_rate == pytest.approx(0.5)
    assert grading.excluded.non_standard == 1
    assert grading.excluded.awaiting == 1
    assert grading.pass_snapshotted == 1
    assert [t.tier for t in grading.tiers] == ["LOCK", "STRONG", "LEAN"]
    assert _tier(grading, "LOCK").decided == 0
    assert _tier(grading, "LOCK").hit_rate is None


def test_an_accruing_tier_stays_neutral_and_counts_mature_days_only():
    rows = [_snap(i) for i in range(150)] + [_snap(1000 + i, snapshot_at=FRESH_DAY) for i in range(100)]

    lean = _tier(build_tier_grading(rows, {}, AS_OF, GRADED_AT), "LEAN")

    assert lean.decided == 250
    assert lean.hit_rate == 1.0
    assert lean.verdict == "accruing"
    assert lean.verdict_sample_size == 150
    assert lean.signal == "neutral"


def test_a_full_sample_reads_its_verdict():
    rows = [_snap(i, recommendation="OVER") for i in range(200)]

    grading = build_tier_grading(rows, {}, AS_OF, GRADED_AT)
    lean = _tier(grading, "LEAN")

    assert lean.verdict == "reject"
    assert lean.verdict_hit_rate == 0.0
    assert grading.projection_version == "props-v2"
    assert grading.verdict_sample == 200

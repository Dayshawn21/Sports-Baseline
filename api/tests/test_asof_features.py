"""As-of-date features must never see past the cutoff.

The bug this replaces: the h2h table is a running total, so a 2023 match was handed a
head-to-head record that already counted the match being predicted. Every assertion
here is really the same assertion — nothing after `before` may influence the result.
"""

import datetime as dt

import pytest

from app.ml.asof_features import HistoryIndex, h2h_win_pct

D = dt.date

# p1=1, p2=2, p3=3. Columns: (match_date, p1_id, p2_id, winner_id, surface)
ROWS = [
    (D(2024, 1, 1), 1, 2, 1, "hard"),
    (D(2024, 2, 1), 1, 2, 2, "clay"),
    (D(2024, 3, 1), 1, 3, 1, "hard"),
    (D(2024, 4, 1), 1, 2, 1, "hard"),
    (D(2024, 5, 1), 2, 3, 2, "clay"),
    (D(2024, 6, 1), 1, 2, 2, "grass"),
]


@pytest.fixture
def idx() -> HistoryIndex:
    return HistoryIndex(ROWS)


class TestPrior:
    def test_only_matches_before_the_cutoff_are_visible(self, idx):
        assert len(idx.prior(1, D(2024, 3, 1))) == 2

    def test_the_cutoff_itself_is_excluded(self, idx):
        # The match on 2024-01-01 must not be visible when predicting it.
        assert idx.prior(1, D(2024, 1, 1)) == []

    def test_an_unknown_player_has_no_history(self, idx):
        assert idx.prior(999, D(2025, 1, 1)) == []

    def test_history_is_ordered_by_date(self, idx):
        dates = [m.date for m in idx.prior(1, D(2025, 1, 1))]
        assert dates == sorted(dates)


class TestH2H:
    def test_a_first_meeting_has_no_prior_record(self, idx):
        assert idx.h2h(1, 2, D(2024, 1, 1)) == (0, 0)

    def test_only_meetings_before_the_cutoff_are_counted(self, idx):
        assert idx.h2h(1, 2, D(2024, 4, 1)) == (1, 1)

    def test_the_full_record_accumulates_over_time(self, idx):
        assert idx.h2h(1, 2, D(2025, 1, 1)) == (2, 2)

    def test_the_record_is_symmetric_when_reversed(self, idx):
        assert idx.h2h(2, 1, D(2025, 1, 1)) == (2, 2)

    def test_other_opponents_are_excluded(self, idx):
        assert idx.h2h(1, 3, D(2025, 1, 1)) == (1, 0)

    def test_surface_filters_the_record(self, idx):
        assert idx.h2h(1, 2, D(2025, 1, 1), surface="hard") == (2, 0)
        assert idx.h2h(1, 2, D(2025, 1, 1), surface="clay") == (0, 1)

    def test_win_pct_is_none_before_they_have_met(self):
        assert h2h_win_pct(0, 0) is None

    def test_win_pct_is_the_share_of_meetings(self):
        assert h2h_win_pct(3, 1) == pytest.approx(0.75)


class TestForm:
    def test_a_debutant_has_no_form(self, idx):
        f = idx.form(1, D(2024, 1, 1), "hard")
        assert f["experience"] == 0.0
        assert f["rest_days"] is None
        assert f["win_rate_last_20"] is None

    def test_experience_counts_prior_matches_only(self, idx):
        assert idx.form(1, D(2024, 4, 1), "hard")["experience"] == 3.0

    def test_rest_days_measure_back_to_the_previous_match(self, idx):
        assert idx.form(1, D(2024, 3, 1), "hard")["rest_days"] == 29.0

    def test_win_rate_uses_results_before_the_cutoff(self, idx):
        # p1 before 2024-04-01: won, lost, won.
        assert idx.form(1, D(2024, 4, 1), "hard")["win_rate_last_20"] == pytest.approx(2 / 3)

    def test_surface_win_rate_is_surface_specific(self, idx):
        # p1 on hard before 2024-04-01: one match, won.
        assert idx.form(1, D(2024, 4, 1), "hard")["win_rate_surface"] == pytest.approx(1.0)

    def test_surface_win_rate_is_none_on_an_unplayed_surface(self, idx):
        assert idx.form(1, D(2024, 4, 1), "grass")["win_rate_surface"] is None

    def test_a_winning_streak_counts_consecutive_wins(self, idx):
        # p1 before 2024-05-01: W, L, W, W. The trailing run is two wins.
        assert idx.form(1, D(2024, 5, 1), "hard")["streak"] == 2.0

    def test_a_losing_streak_is_negative(self, idx):
        # p1 lost on 2024-02-01, and that is the most recent result before 2024-03-01.
        assert idx.form(1, D(2024, 3, 1), "hard")["streak"] == -1.0

    def test_recent_activity_windows_respect_the_cutoff(self, idx):
        f = idx.form(1, D(2024, 2, 15), "hard")
        assert f["matches_30d"] == 1.0
        assert f["matches_10d"] == 0.0


class TestNoLookahead:
    def test_adding_later_matches_never_changes_an_earlier_row(self):
        early = HistoryIndex(ROWS[:3])
        full = HistoryIndex(ROWS)
        cutoff = D(2024, 3, 1)
        assert early.h2h(1, 2, cutoff) == full.h2h(1, 2, cutoff)
        assert early.form(1, cutoff, "hard") == full.form(1, cutoff, "hard")

    def test_the_match_being_predicted_is_never_in_its_own_features(self):
        # The regression that motivated this module.
        for match_date, p1, p2, _winner, surface in ROWS:
            before = HistoryIndex(ROWS).h2h(p1, p2, match_date, surface=None)
            played_before = sum(
                1 for d, a, b, _w, _s in ROWS
                if d < match_date and {a, b} == {p1, p2}
            )
            assert sum(before) == played_before

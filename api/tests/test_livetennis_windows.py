"""A wide backfill window must be sliced, or it silently loses rows.

_get_paginated stops at MAX_PAGES * PAGE_LIMIT (5,000) per query. The archive holds
roughly 550 matches per tour per month, so a multi-year window in one query would drop
everything past the ceiling with only a warning.
"""

import datetime as dt

from app.ingest.livetennis import _windows


D = dt.date


class TestWindows:
    def test_no_chunking_returns_the_range_unchanged(self):
        assert _windows(D(2025, 1, 1), D(2025, 12, 31), 0) == [(D(2025, 1, 1), D(2025, 12, 31))]

    def test_negative_chunk_is_treated_as_no_chunking(self):
        assert _windows(D(2025, 1, 1), D(2025, 3, 1), -5) == [(D(2025, 1, 1), D(2025, 3, 1))]

    def test_a_range_shorter_than_the_chunk_stays_whole(self):
        assert _windows(D(2025, 1, 1), D(2025, 1, 10), 30) == [(D(2025, 1, 1), D(2025, 1, 10))]

    def test_windows_are_inclusive_and_do_not_overlap(self):
        out = _windows(D(2025, 1, 1), D(2025, 1, 10), 4)
        assert out == [
            (D(2025, 1, 1), D(2025, 1, 4)),
            (D(2025, 1, 5), D(2025, 1, 8)),
            (D(2025, 1, 9), D(2025, 1, 10)),
        ]

    def test_windows_cover_every_day_exactly_once(self):
        start, end, chunk = D(2024, 1, 1), D(2024, 6, 30), 30
        seen: list[dt.date] = []
        for a, b in _windows(start, end, chunk):
            d = a
            while d <= b:
                seen.append(d)
                d += dt.timedelta(days=1)
        expected = (end - start).days + 1
        assert len(seen) == expected
        assert len(set(seen)) == expected
        assert min(seen) == start and max(seen) == end

    def test_no_window_exceeds_the_chunk_size(self):
        for a, b in _windows(D(2023, 1, 1), D(2026, 8, 1), 30):
            assert (b - a).days + 1 <= 30

    def test_a_single_day_range_yields_one_window(self):
        assert _windows(D(2025, 5, 5), D(2025, 5, 5), 30) == [(D(2025, 5, 5), D(2025, 5, 5))]

    def test_an_inverted_range_is_left_alone(self):
        assert _windows(D(2025, 5, 5), D(2025, 1, 1), 30) == [(D(2025, 5, 5), D(2025, 1, 1))]

    def test_three_years_of_month_slices_stays_well_under_the_page_ceiling(self):
        # ~1,050 matches/month across both tours, fetched per tour, vs a 5,000 ceiling.
        assert len(_windows(D(2023, 1, 1), D(2026, 1, 1), 30)) >= 36

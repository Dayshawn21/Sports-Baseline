import datetime as dt

from app.ingest.prizepicks import link_date_utc


def _parsed(raw: str) -> dt.datetime:
    """Parse the way the PrizePicks ingest does, preserving the sent offset."""
    return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))


def test_et_evening_start_resolves_to_the_next_utc_day():
    # 21:00 ET is 01:00 UTC the following day. Reading the day off the ET value
    # sent the lookup to 08-28, where it found a finished match.
    assert link_date_utc(_parsed("2026-08-28T21:00:00.000-04:00")) == dt.date(2026, 8, 29)


def test_et_morning_start_keeps_the_same_utc_day():
    assert link_date_utc(_parsed("2026-08-28T11:00:00.000-04:00")) == dt.date(2026, 8, 28)


def test_utc_value_is_unchanged():
    assert link_date_utc(_parsed("2026-08-29T01:00:00.000Z")) == dt.date(2026, 8, 29)


def test_naive_datetime_is_read_as_utc():
    assert link_date_utc(dt.datetime(2026, 8, 29, 1, 0)) == dt.date(2026, 8, 29)


def test_string_start_time_falls_back_to_the_leading_date():
    assert link_date_utc("2026-08-29T01:00:00+00:00") == dt.date(2026, 8, 29)

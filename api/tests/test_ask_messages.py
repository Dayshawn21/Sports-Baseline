import datetime as dt

import pytest
from anthropic.types import Usage

from app.core.ask_messages import AskUsage, stop_for, tool_result_block, user_turn


def test_user_turn_leads_with_the_central_date_and_time():
    now = dt.datetime(2026, 10, 27, 20, 5, tzinfo=dt.UTC)
    assert user_turn("Who plays tonight?", now) == (
        "Today is Tuesday, October 27, 2026, 3:05 PM CT.\n\nWho plays tonight?"
    )


def test_user_turn_follows_daylight_saving():
    # Standard time from 2026-11-01: 20:05 UTC is 2:05 PM CST, not 3:05.
    now = dt.datetime(2026, 11, 3, 20, 5, tzinfo=dt.UTC)
    assert user_turn("q", now).startswith("Today is Tuesday, November 3, 2026, 2:05 PM CT.")


def test_user_turn_reads_midnight_and_noon_as_twelve():
    assert "12:00 AM CT" in user_turn("q", dt.datetime(2026, 10, 28, 5, 0, tzinfo=dt.UTC))
    assert "12:00 PM CT" in user_turn("q", dt.datetime(2026, 10, 28, 17, 0, tzinfo=dt.UTC))


def test_tool_result_block_omits_is_error_unless_true():
    assert tool_result_block("toolu_1", '{"ok": 1}') == {
        "type": "tool_result",
        "tool_use_id": "toolu_1",
        "content": '{"ok": 1}',
    }


def test_tool_result_block_marks_an_error():
    block = tool_result_block("toolu_2", "get_slate: week: bad", is_error=True)
    assert block["is_error"] is True
    assert block["tool_use_id"] == "toolu_2"


def test_usage_sums_requests_and_treats_missing_cache_fields_as_zero():
    usage = AskUsage()
    usage.add(Usage(input_tokens=1200, output_tokens=80))
    usage.add(Usage(
        input_tokens=40, output_tokens=150,
        cache_read_input_tokens=3000, cache_creation_input_tokens=0,
    ))
    assert usage == AskUsage(
        requests=2, input_tokens=1240, output_tokens=230,
        cache_read_input_tokens=3000, cache_creation_input_tokens=0,
    )


def test_new_usage_is_all_zero():
    assert AskUsage() == AskUsage(0, 0, 0, 0, 0)


@pytest.mark.parametrize(("reason", "stop"), [
    ("end_turn", "answered"),
    ("max_tokens", "truncated"),
    ("refusal", "refused"),
    ("tool_use", None),
    ("pause_turn", "error"),
    ("stop_sequence", "error"),
    ("model_context_window_exceeded", "error"),
    (None, "error"),
    ("something_new", "error"),
])
def test_stop_for_maps_every_reason(reason, stop):
    assert stop_for(reason) == stop

from app.services.nfl.props_provider import DEFAULT_PRIZEPICKS_POLL_INTERVAL_MINUTES


def test_prizepicks_default_poll_interval_respects_two_hour_limit() -> None:
    assert DEFAULT_PRIZEPICKS_POLL_INTERVAL_MINUTES == 120

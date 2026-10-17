from datetime import UTC, datetime

from app.nfl.weather import NFL_STADIUMS, forecast_at_kickoff, stadium_for_home_team


def test_stadium_registry_covers_all_nfl_teams_and_uses_known_venue_types() -> None:
    assert len(NFL_STADIUMS) == 32
    assert {stadium.venue_type for stadium in NFL_STADIUMS.values()} == {"outdoor", "dome", "retractable"}


def test_stadium_registry_marks_domes_and_retractable_roofs_without_outdoor_assumptions() -> None:
    assert stadium_for_home_team("DET").venue_type == "dome"
    assert stadium_for_home_team("ARI").venue_type == "retractable"
    assert stadium_for_home_team("XXX") is None


def test_forecast_uses_the_kickoff_hour_and_preserves_imperial_values() -> None:
    forecast = forecast_at_kickoff({"hourly": {"time": ["2026-09-20T20:00"], "temperature_2m": [61], "wind_speed_10m": [14], "wind_gusts_10m": [22], "precipitation_probability": [45]}}, datetime(2026, 9, 20, 20, 15, tzinfo=UTC))

    assert forecast is not None
    assert (forecast.temperature_f, forecast.wind_mph, forecast.wind_gust_mph, forecast.precipitation_probability) == (61, 14, 22, 45)

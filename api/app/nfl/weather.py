"""Stable NFL stadium metadata used to resolve weather forecasts by home team."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

VenueType = Literal["outdoor", "dome", "retractable"]


@dataclass(frozen=True)
class NflStadium:
    latitude: float
    longitude: float
    venue_type: VenueType


@dataclass(frozen=True)
class NflWeatherForecast:
    forecast_for: datetime
    temperature_f: float | None
    wind_mph: float | None
    wind_gust_mph: float | None
    precipitation_probability: float | None


# Team codes match the NFLverse schedule ingest. Retractable roofs remain unknown
# at display time because a forecast cannot tell whether the roof will be closed.
NFL_STADIUMS: dict[str, NflStadium] = {
    "ARI": NflStadium(33.5276, -112.2626, "retractable"), "ATL": NflStadium(33.7554, -84.4008, "retractable"),
    "BAL": NflStadium(39.2780, -76.6227, "outdoor"), "BUF": NflStadium(42.7738, -78.7870, "outdoor"),
    "CAR": NflStadium(35.2258, -80.8528, "outdoor"), "CHI": NflStadium(41.8623, -87.6167, "outdoor"),
    "CIN": NflStadium(39.0954, -84.5160, "outdoor"), "CLE": NflStadium(41.5061, -81.6995, "outdoor"),
    "DAL": NflStadium(32.7473, -97.0945, "retractable"), "DEN": NflStadium(39.7439, -105.0201, "outdoor"),
    "DET": NflStadium(42.3400, -83.0456, "dome"), "GB": NflStadium(44.5013, -88.0622, "outdoor"),
    "HOU": NflStadium(29.6847, -95.4107, "retractable"), "IND": NflStadium(39.7601, -86.1639, "retractable"),
    "JAX": NflStadium(30.3239, -81.6373, "outdoor"), "KC": NflStadium(39.0489, -94.4839, "outdoor"),
    "LA": NflStadium(33.9535, -118.3392, "dome"), "LAC": NflStadium(33.9535, -118.3392, "dome"),
    "LV": NflStadium(36.0909, -115.1833, "dome"), "MIA": NflStadium(25.9580, -80.2389, "outdoor"),
    "MIN": NflStadium(44.9738, -93.2581, "dome"), "NE": NflStadium(42.0909, -71.2643, "outdoor"),
    "NO": NflStadium(29.9511, -90.0812, "dome"), "NYG": NflStadium(40.8135, -74.0745, "outdoor"),
    "NYJ": NflStadium(40.8135, -74.0745, "outdoor"), "PHI": NflStadium(39.9008, -75.1675, "outdoor"),
    "PIT": NflStadium(40.4468, -80.0158, "outdoor"), "SEA": NflStadium(47.5952, -122.3316, "outdoor"),
    "SF": NflStadium(37.4030, -121.9700, "outdoor"), "TB": NflStadium(27.9759, -82.5033, "outdoor"),
    "TEN": NflStadium(36.1665, -86.7713, "outdoor"), "WAS": NflStadium(38.9078, -76.8645, "outdoor"),
}


def stadium_for_home_team(team_code: str) -> NflStadium | None:
    return NFL_STADIUMS.get(team_code)


def forecast_at_kickoff(payload: dict[str, object], kickoff: datetime) -> NflWeatherForecast | None:
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        return None
    times = hourly.get("time")
    if not isinstance(times, list):
        return None
    target = kickoff.replace(minute=0, second=0, microsecond=0).replace(tzinfo=None).isoformat(timespec="minutes")
    try:
        index = times.index(target)
    except ValueError:
        return None

    def value(name: str) -> float | None:
        values = hourly.get(name)
        raw = values[index] if isinstance(values, list) and len(values) > index else None
        return float(raw) if isinstance(raw, int | float) else None

    return NflWeatherForecast(kickoff, value("temperature_2m"), value("wind_speed_10m"), value("wind_gusts_10m"), value("precipitation_probability"))

from datetime import date

import pytest
from fastapi import HTTPException

from app.core.model_season import MODEL_FIRST_SEASON, is_model_season
from app.season_query import model_season, optional_model_season

TODAY = date(2026, 11, 6)


@pytest.mark.parametrize("season", [MODEL_FIRST_SEASON, 2025, 2026])
def test_seasons_from_the_first_through_this_year_are_model_seasons(season: int) -> None:
    assert is_model_season(season, TODAY)


@pytest.mark.parametrize("season", [MODEL_FIRST_SEASON - 1, 2027, 0, -1, 2**31])
def test_other_seasons_are_not(season: int) -> None:
    assert not is_model_season(season, TODAY)


def test_the_query_dependency_422s_an_unknown_season() -> None:
    with pytest.raises(HTTPException) as err:
        model_season(MODEL_FIRST_SEASON - 1)
    assert err.value.status_code == 422


def test_an_omitted_optional_season_passes_through() -> None:
    assert optional_model_season(None) is None
    assert optional_model_season(MODEL_FIRST_SEASON) == MODEL_FIRST_SEASON

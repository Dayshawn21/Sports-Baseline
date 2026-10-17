"""best_of must reach the projection layer from the linked match.

The core projection functions are already best-of-5 aware, but the read path
never carried the format, so every men's Slam prop was projected as best-of-3.
"""
import inspect

import pytest

from app.repositories import props as props_repo
from app.repositories.props import Prop


def test_prop_exposes_best_of_defaulting_to_none():
    # None, not 3: an unlinked prop has no format, and a caller defaulting to 3
    # should be making that choice explicitly rather than reading it as fact.
    fields = Prop.__dataclass_fields__
    assert "best_of" in fields
    assert fields["best_of"].default is None


def test_prop_best_of_is_the_last_positional_field():
    # Both queries build rows with Prop(*r), so a column added anywhere but the
    # end silently shifts every field after it.
    assert list(Prop.__dataclass_fields__)[-1] == "best_of"


@pytest.mark.parametrize(
    "source_fn",
    [props_repo.get_today_props, props_repo.get_today_match_odds_as_props],
)
def test_every_prop_query_selects_best_of_last(source_fn):
    sql = inspect.getsource(source_fn)
    assert "best_of" in sql, "query does not select best_of"
    # The relinked match wins over the stored link, the same way surface and
    # match_status already resolve, so a re-resolved match carries its own format.
    if source_fn is props_repo.get_today_props:
        assert "COALESCE(relinked.best_of, m.best_of)" in sql
        assert "mm.best_of" in sql, "relinked lateral must select best_of"


def test_prop_accepts_a_best_of_five_match():
    prop = Prop(
        id=1, player_id=1, player_name="A Player", match_id=10, source="prizepicks",
        stat_type="Total Games", line=None, odds_type=None, fetched_at=None,
        start_time=None, best_of=5,
    )
    assert prop.best_of == 5


def test_prop_without_a_linked_match_has_no_format():
    prop = Prop(
        id=1, player_id=1, player_name="A Player", match_id=None, source="prizepicks",
        stat_type="Total Games", line=None, odds_type=None, fetched_at=None,
        start_time=None,
    )
    assert prop.best_of is None

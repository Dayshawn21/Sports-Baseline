"""The compact NFL slate wire body: each history sample written once, nothing lost."""
import json
from datetime import date, timedelta

from app.core.nfl_slate_wire import SAMPLE_FIELDS, compact_slate
from app.schemas.nfl import NflHistoryResultSchema, NflHistorySampleSchema
from app.services.nfl.slate_cache import slate_json
from tests.helpers.nfl_prop_predictions import EMPTY, NOW, _game, _line, _slate
from tests.helpers.nfl_slate_wire import expand_slate


def _sample(*values: float) -> NflHistorySampleSchema:
    results = [NflHistoryResultSchema(value=v, opponent_team="NYJ", game_date=date(2026, 9, 1 + i)) for i, v in enumerate(values)]
    return NflHistorySampleSchema(average=sum(values) / len(values), values=results)


FORM, LONG, ALLOWED = _sample(60, 70), _sample(60, 70, 80), _sample(45.5)


def _week():
    # Lines 10-12 are one player's demon, goblin and standard lines: same samples.
    same_player = [
        _line(i, player_id=7, recent_form=FORM, recent_form_long=LONG, opponent_allowed_history=ALLOWED, odds_type=t)
        for i, t in ((10, "demon"), (11, "goblin"), (12, "standard"))
    ]
    other = _line(20, recent_form=_sample(12), opponent_allowed_history=ALLOWED)
    return _slate(_game(1, NOW + timedelta(hours=2), [*same_player, other]), _game(2, None, []))


def _full(slate) -> dict:
    return slate.model_dump(mode="json", by_alias=True)


def test_identical_samples_share_one_index():
    body = compact_slate(_full(_week()))
    lines = body["games"][0]["lines"]

    assert {line["recentForm"] for line in lines[:3]} == {lines[0]["recentForm"]}
    assert lines[0]["opponentAllowedHistory"] == lines[3]["opponentAllowedHistory"]
    assert lines[3]["recentForm"] != lines[0]["recentForm"]
    # FORM, LONG, ALLOWED, EMPTY (opponent history) and line 20's own form.
    assert len(body["samples"]) == 5


def test_expanding_gives_back_the_original_exactly():
    full = _full(_week())

    assert expand_slate(compact_slate(full)) == full


def test_a_missing_sample_stays_missing():
    body = compact_slate(_full(_week()))
    other = body["games"][0]["lines"][3]

    assert other["recentFormLong"] is None


def test_only_the_sample_fields_change():
    full = _full(_week())
    body = compact_slate(full)

    for before, after in zip(full["games"][0]["lines"], body["games"][0]["lines"]):
        assert {k: v for k, v in before.items() if k not in SAMPLE_FIELDS} == {
            k: v for k, v in after.items() if k not in SAMPLE_FIELDS
        }
        assert all(isinstance(after[k], int) or after[k] is None for k in SAMPLE_FIELDS)
    assert {k: v for k, v in full.items() if k != "games"} == {k: v for k, v in body.items() if k not in ("games", "samples")}
    assert {k: v for k, v in full["games"][1].items()} == body["games"][1]


def test_a_week_without_lines_has_no_samples():
    body = compact_slate(_full(_slate(_game(1, None, []))))

    assert body["samples"] == []


def test_the_served_body_is_compact_json():
    text = slate_json(_week()).decode()

    assert ": " not in text and ", " not in text
    assert expand_slate(json.loads(text)) == _full(_week())


def test_the_repeated_samples_no_longer_scale_with_lines():
    many = _slate(_game(1, NOW, [
        _line(i, player_id=7, recent_form=FORM, recent_form_long=LONG, opponent_allowed_history=ALLOWED, opponent_history=EMPTY)
        for i in range(200)
    ]))

    full_size = len(json.dumps(_full(many)))
    compact_size = len(slate_json(many))

    assert compact_size < full_size * 0.7

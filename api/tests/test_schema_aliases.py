"""
The H2H fields serialize through to_camel, which capitalizes the letter after a
digit and turns `h2h_p1_wins` into `h2HP1Wins`. The web client reads `h2hP1Wins`,
so that mismatch silently rendered every head-to-head record as undefined.

These assert the wire format rather than the Python field, which is the check
that was missing when the bug shipped.
"""
import pytest
from pydantic import BaseModel

from app.schemas import tennis as schemas

H2H_MODELS = [schemas.MatchPrediction, schemas.MatchBestPicksSchema]


@pytest.mark.parametrize("model", H2H_MODELS, ids=lambda m: m.__name__)
def test_h2h_fields_serialize_with_lowercase_h2h(model):
    aliases = {name: f.alias for name, f in model.model_fields.items() if "h2h" in name}

    assert aliases == {"h2h_p1_wins": "h2hP1Wins", "h2h_p2_wins": "h2hP2Wins"}


def test_prediction_dump_uses_client_h2h_keys():
    dumped = _sample(schemas.MatchPrediction).model_dump(by_alias=True)

    assert dumped["h2hP1Wins"] == 2
    assert dumped["h2hP2Wins"] == 0
    assert "h2HP1Wins" not in dumped


def _expected_camel(field_name: str) -> str:
    """Plain snake to camel: capitalize each word's first letter, digits untouched."""
    head, *rest = field_name.split("_")
    return head + "".join(word[:1].upper() + word[1:] for word in rest)


def test_every_alias_matches_plain_camel_case():
    """h2h was the only field whose alias drifted from plain camelCase; keep it that way."""
    broken = []
    for model in vars(schemas).values():
        if not (isinstance(model, type) and issubclass(model, BaseModel)):
            continue
        if not model.__module__.startswith("app."):
            continue
        for name, field in model.model_fields.items():
            if field.alias is None:
                continue
            expected = _expected_camel(name)
            if field.alias != expected:
                broken.append((model.__name__, name, field.alias, expected))

    assert broken == []


def _sample(model):
    """Build a model instance by field name, filling required fields minimally."""
    values = {}
    for name, field in model.model_fields.items():
        if not field.is_required():
            continue
        if name == "h2h_p1_wins":
            values[name] = 2
        elif name == "h2h_p2_wins":
            values[name] = 0
        else:
            values[name] = _placeholder(field.annotation)
    return model(**values)


def _placeholder(annotation):
    origin = getattr(annotation, "__origin__", None)
    if annotation is int:
        return 0
    if annotation is str:
        return ""
    if annotation is float:
        return 0.0
    if origin is list or annotation is list:
        return []
    if origin is dict or annotation is dict:
        return {}
    return None

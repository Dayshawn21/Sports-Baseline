import json
from pathlib import Path

import pytest

from thumbnails import config as tc


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    out = tmp_path / "output"
    out.mkdir()
    (out / "week01-dal-feed.png").write_bytes(b"\x89PNG")
    (out / "notes.txt").write_text("x")
    return out


def raw(**overrides) -> dict:
    base = {"headline": "Can Dallas save it?", "chart": "week01-dal-feed.png", "sport": "nfl"}
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def parse(output_dir: Path, config_path: Path | None = None, **overrides) -> tc.ThumbnailConfig:
    path = config_path or output_dir.parent / "configs" / "week01-dal.json"
    return tc.parse_config(raw(**overrides), config_path=path, output_dir=output_dir)


def test_minimal_config_defaults_name_from_file(output_dir):
    config = parse(output_dir)
    assert config.name == "week01-dal"
    assert config.chart == (output_dir / "week01-dal-feed.png").resolve()
    assert config.sport_tag == "NFL"
    assert (config.subline, config.callout, config.background) == (None, None, None)


def test_full_config(output_dir, tmp_path):
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "bg.jpg").write_bytes(b"jpg")
    config = parse(output_dir, subline="Week 7 check-in", name="dal-custom", sport="tennis",
                   callout={"value": "+1.8", "label": "wins better than their record"},
                   background="bg.jpg")
    assert config.name == "dal-custom"
    assert config.callout == tc.Callout("+1.8", "wins better than their record")
    assert config.background == (tmp_path / "configs" / "bg.jpg").resolve()
    assert config.sport_tag == "TENNIS"


@pytest.mark.parametrize("headline", ["Too short", "This one has far too many words"])
def test_headline_must_be_three_to_five_words(output_dir, headline):
    with pytest.raises(tc.ConfigError, match="3 to 5 words"):
        parse(output_dir, headline=headline)


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"headline": None}, "'headline' is required"),
        ({"sport": "nhl"}, "'sport' must be one of"),
        ({"chart": "missing.png"}, "not found"),
        ({"chart": "notes.txt"}, "must be a PNG"),
        ({"chart": "../outside.png"}, "inside"),
        ({"subline": "x" * 61}, "at most 60"),
        ({"callout": {"value": "+1.8"}}, "exactly 'value' and 'label'"),
        ({"callout": {"value": "123456789", "label": "x"}}, "at most 8"),
        ({"background": "nope.jpg"}, "'background' not found"),
        ({"name": "Week 1"}, "lowercase"),
        ({"headlin": "typo here now"}, "unknown field"),
        ({"headline": 42}, "non-empty text"),
    ],
)
def test_invalid_configs_explain_themselves(output_dir, overrides, message):
    with pytest.raises(tc.ConfigError, match=message):
        parse(output_dir, **overrides)


def test_load_config_reads_json_and_reports_bad_json(output_dir, tmp_path):
    good = tmp_path / "sample-post.json"
    good.write_text(json.dumps(raw()))
    assert tc.load_config(good, output_dir=output_dir).name == "sample-post"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(tc.ConfigError, match="not valid JSON"):
        tc.load_config(bad, output_dir=output_dir)
    with pytest.raises(tc.ConfigError, match="config not found"):
        tc.load_config(tmp_path / "missing.json", output_dir=output_dir)


def test_output_paths():
    assert tc.output_path("week01-dal", "youtube") == tc.THUMBNAIL_DIR / "week01-dal-youtube.png"
    with pytest.raises(tc.ConfigError):
        tc.output_path("week01-dal", "tiktok")


@pytest.mark.parametrize("name", tc.FORMAT_NAMES)
def test_safe_boxes_leave_room_inside_each_canvas(name):
    fmt = tc.FORMATS[name]
    assert fmt.safe.left + fmt.safe.right < fmt.width / 2
    assert fmt.safe.top + fmt.safe.bottom < fmt.height / 2
    assert fmt.headline_max_px > tc.HEADLINE_MIN_PX


def test_platform_sizes():
    assert {n: (f.width, f.height) for n, f in tc.FORMATS.items()} == {
        "youtube": (1280, 720), "vertical": (1080, 1920), "feed": (1080, 1350)}
    assert tc.FORMATS["youtube"].clear_bottom_right == (240, 110)

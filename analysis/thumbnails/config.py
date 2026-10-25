"""Thumbnail config: one small JSON file per post, validated before anything renders."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

ANALYSIS_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ANALYSIS_DIR / "output"
THUMBNAIL_DIR = OUTPUT_DIR / "thumbnails"

Sport = Literal["nfl", "nba", "tennis"]
SPORT_TAGS: dict[str, str] = {"nfl": "NFL", "nba": "NBA", "tennis": "TENNIS"}

HEADLINE_WORDS = (3, 5)
SUBLINE_MAX = 60
CALLOUT_VALUE_MAX = 8
CALLOUT_LABEL_MAX = 40
FIELDS = {"headline", "subline", "chart", "sport", "callout", "background", "name"}
NAME_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]*")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Insets:
    top: int
    right: int
    bottom: int
    left: int


@dataclass(frozen=True)
class Format:
    width: int
    height: int
    safe: Insets
    headline_max_px: int
    # Corner a platform covers with its own UI (YouTube's video length), as width, height.
    clear_bottom_right: tuple[int, int] | None = None


HEADLINE_MIN_PX = 64
FORMATS: dict[str, Format] = {
    "youtube": Format(1280, 720, Insets(56, 64, 56, 64), 132, clear_bottom_right=(240, 110)),
    # TikTok and Reels cover the top bar, caption and button column; profile grids
    # crop covers to 3:4, which trims 240 px from the top and bottom.
    "vertical": Format(1080, 1920, Insets(240, 140, 420, 60), 150),
    # The 3:4 Instagram grid crop trims about 34 px from each side of a 4:5 post.
    "feed": Format(1080, 1350, Insets(60, 80, 60, 80), 140),
}
FORMAT_NAMES = tuple(FORMATS)


@dataclass(frozen=True)
class Callout:
    value: str
    label: str


@dataclass(frozen=True)
class ThumbnailConfig:
    headline: str
    chart: Path
    sport: Sport
    name: str
    subline: str | None = None
    callout: Callout | None = None
    background: Path | None = None

    @property
    def sport_tag(self) -> str:
        return SPORT_TAGS[self.sport]


def _text(raw: dict, key: str, *, required: bool) -> str | None:
    value = raw.get(key)
    if value is None:
        if required:
            raise ConfigError(f"'{key}' is required")
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"'{key}' must be non-empty text")
    return value.strip()


def _headline(raw: dict) -> str:
    headline = _text(raw, "headline", required=True)
    words = len(headline.split())
    low, high = HEADLINE_WORDS
    if not low <= words <= high:
        raise ConfigError(f"'headline' must be {low} to {high} words, got {words}: {headline!r}")
    return headline


def _chart(raw: dict, output_dir: Path) -> Path:
    name = _text(raw, "chart", required=True)
    chart = (output_dir / name).resolve()
    if output_dir.resolve() not in chart.parents:
        raise ConfigError(f"'chart' must be a file inside {output_dir}: {name!r}")
    if chart.suffix.lower() != ".png":
        raise ConfigError(f"'chart' must be a PNG: {name!r}")
    if not chart.is_file():
        raise ConfigError(f"'chart' not found: {chart} (export the chart first)")
    return chart


def _callout(raw: dict) -> Callout | None:
    callout = raw.get("callout")
    if callout is None:
        return None
    if not isinstance(callout, dict) or set(callout) != {"value", "label"}:
        raise ConfigError("'callout' must be an object with exactly 'value' and 'label'")
    value, label = _text(callout, "value", required=True), _text(callout, "label", required=True)
    if len(value) > CALLOUT_VALUE_MAX or len(label) > CALLOUT_LABEL_MAX:
        raise ConfigError(
            f"'callout' value is at most {CALLOUT_VALUE_MAX} characters and label {CALLOUT_LABEL_MAX}"
        )
    return Callout(value, label)


def _background(raw: dict, config_dir: Path) -> Path | None:
    name = _text(raw, "background", required=False)
    if name is None:
        return None
    background = (config_dir / name).resolve()
    if not background.is_file():
        raise ConfigError(f"'background' not found: {background}")
    return background


def parse_config(raw: object, *, config_path: Path, output_dir: Path = OUTPUT_DIR) -> ThumbnailConfig:
    if not isinstance(raw, dict):
        raise ConfigError("the config must be a JSON object")
    unknown = set(raw) - FIELDS
    if unknown:
        raise ConfigError(f"unknown field(s): {', '.join(sorted(unknown))}")

    sport = _text(raw, "sport", required=True)
    if sport not in get_args(Sport):
        raise ConfigError(f"'sport' must be one of {', '.join(get_args(Sport))}, got {sport!r}")
    subline = _text(raw, "subline", required=False)
    if subline and len(subline) > SUBLINE_MAX:
        raise ConfigError(f"'subline' is at most {SUBLINE_MAX} characters")
    name = _text(raw, "name", required=False) or config_path.stem
    if not NAME_PATTERN.fullmatch(name):
        raise ConfigError(f"'name' must be lowercase letters, digits and hyphens: {name!r}")

    return ThumbnailConfig(
        headline=_headline(raw),
        chart=_chart(raw, output_dir),
        sport=sport,
        name=name,
        subline=subline,
        callout=_callout(raw),
        background=_background(raw, config_path.parent),
    )


def load_config(path: Path | str, *, output_dir: Path = OUTPUT_DIR) -> ThumbnailConfig:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ConfigError(f"{path} is not valid JSON: {error}") from error
    return parse_config(raw, config_path=path, output_dir=output_dir)


def output_path(name: str, format_name: str) -> Path:
    if format_name not in FORMATS:
        raise ConfigError(f"unknown format {format_name!r}; use {', '.join(FORMAT_NAMES)}")
    return THUMBNAIL_DIR / f"{name}-{format_name}.png"

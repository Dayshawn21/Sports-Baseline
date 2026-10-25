import asyncio
import re
from pathlib import Path

import matplotlib.image as mpimg
import numpy as np
import pytest

from thumbnails import config as tc
from thumbnails import make_thumbnail as mt


def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            playwright.chromium.launch().close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _chromium_available(),
    reason="Chromium for Playwright is not installed: analysis/.venv/Scripts/python -m playwright install chromium",
)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch) -> Path:
    output = tmp_path / "output"
    output.mkdir()
    mpimg.imsave(output / "chart.png", np.full((540, 432, 3), 0.2))
    monkeypatch.setattr(tc, "THUMBNAIL_DIR", output / "thumbnails")
    return tmp_path


def make_config(workspace: Path, headline: str, **extra) -> tc.ThumbnailConfig:
    raw = {"headline": headline, "chart": "chart.png", "sport": "nba", **extra}
    return tc.parse_config(raw, config_path=workspace / "post.json", output_dir=workspace / "output")


def headline_sizes(log: list[str]) -> dict[str, int]:
    found = (re.search(r"-(\w+)\.png \(headline (\d+)px", line) for line in log)
    return {m.group(1): int(m.group(2)) for m in found if m}


def test_renders_every_format_at_its_exact_size_offline(workspace):
    log: list[str] = []
    paths = mt.render(make_config(workspace, "Real or just lucky?"), log=log.append)
    assert [p.name for p in paths] == ["post-youtube.png", "post-vertical.png", "post-feed.png"]
    for path, name in zip(paths, tc.FORMAT_NAMES):
        height, width = mpimg.imread(path).shape[:2]
        assert (width, height) == (tc.FORMATS[name].width, tc.FORMATS[name].height)
    assert "network requests blocked: 0" in log


def test_long_headline_shrinks_but_stays_on_two_lines(workspace):
    log: list[str] = []
    mt.render(make_config(workspace, "Can Philadelphia's defense recover quickly?"), ["youtube"],
              log=log.append)
    size = headline_sizes(log)["youtube"]
    assert tc.HEADLINE_MIN_PX <= size < tc.FORMATS["youtube"].headline_max_px
    assert "2 line(s)" in log[0]


def test_headline_that_cannot_fit_fails_without_writing(workspace):
    words = "Supercalifragilistic Antidisestablishmentarianism Pneumonoultramicroscopic Floccinaucinihilipilification Hippopotomonstrosesquippedaliophobia"
    with pytest.raises(mt.HeadlineTooLong, match="shorten the headline"):
        mt.render(make_config(workspace, words), ["feed"], log=lambda _: None)
    assert not tc.output_path("post", "feed").exists()


def test_background_image_renders(workspace):
    mpimg.imsave(workspace / "bg.png", np.random.default_rng(0).random((90, 160, 3)))
    paths = mt.render(make_config(workspace, "Real or just lucky?", background="bg.png"),
                      ["feed"], log=lambda _: None)
    assert paths[0].is_file()


def test_renders_inside_a_running_event_loop_like_jupyter(workspace):
    async def in_notebook():
        return mt.render(make_config(workspace, "Real or just lucky?"), ["youtube"], log=lambda _: None)

    assert asyncio.run(in_notebook())[0].is_file()

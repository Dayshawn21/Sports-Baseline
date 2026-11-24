"""Render a thumbnail config to PNGs for YouTube, vertical video covers and feed posts.

Run from the repo root:
    analysis/.venv/Scripts/python analysis/thumbnails/make_thumbnail.py --config <file.json>
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable, Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import Route, sync_playwright  # noqa: E402

from lib import style  # noqa: E402
from thumbnails.config import (  # noqa: E402
    FORMAT_NAMES,
    FORMATS,
    HEADLINE_MIN_PX,
    ConfigError,
    ThumbnailConfig,
    load_config,
    output_path,
)

TEMPLATE = Path(__file__).resolve().parent / "template.html"
HEADLINE_STEP_PX = 4


class HeadlineTooLong(ValueError):
    pass


def tokens() -> dict[str, str]:
    return {
        "--accent": style.ACCENT,
        "--bg": style.BG,
        "--text": style.TEXT,
        "--text-2": style.TEXT_2,
        "--gray": style.GRAY,
    }


def page_data(config: ThumbnailConfig, format_name: str) -> dict:
    callout = config.callout
    return {
        "format": format_name,
        "tokens": tokens(),
        "headline": config.headline,
        "subline": config.subline,
        "sportTag": config.sport_tag,
        "callout": {"value": callout.value, "label": callout.label} if callout else None,
        "chart": config.chart.as_uri(),
        "background": config.background.as_uri() if config.background else None,
        "logo": style.LOGO.as_uri(),
        "handle": style.HANDLE,
    }


def render(
    config: ThumbnailConfig,
    formats: Sequence[str] = FORMAT_NAMES,
    *,
    log: Callable[[str], None] = print,
) -> list[Path]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _render(config, formats, log)
    # Jupyter runs an event loop, and Playwright's sync API refuses to start inside one.
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_render, config, formats, log).result()


def _render(config: ThumbnailConfig, formats: Sequence[str], log: Callable[[str], None]) -> list[Path]:
    unknown = [name for name in formats if name not in FORMATS]
    if unknown:
        raise ConfigError(f"unknown format(s) {', '.join(unknown)}; use {', '.join(FORMAT_NAMES)}")
    blocked: list[str] = []

    def offline(route: Route) -> None:
        if route.request.url.startswith("file:"):
            route.continue_()
        else:
            blocked.append(route.request.url)
            route.abort()

    written: list[Path] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for name in formats:
                fmt = FORMATS[name]
                page = browser.new_page(viewport={"width": fmt.width, "height": fmt.height})
                page.route("**/*", offline)
                page.goto(TEMPLATE.as_uri())
                page.evaluate("data => window.fill(data)", page_data(config, name))
                fit = page.evaluate(
                    "([max, min, step]) => window.fitHeadline(max, min, step)",
                    [fmt.headline_max_px, HEADLINE_MIN_PX, HEADLINE_STEP_PX],
                )
                if not fit["fits"]:
                    raise HeadlineTooLong(
                        f"{name}: {config.headline!r} does not fit in two lines at "
                        f"{HEADLINE_MIN_PX}px; shorten the headline"
                    )
                path = output_path(config.name, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                page.locator(".canvas").screenshot(path=path)
                page.close()
                written.append(path)
                log(f"{path} (headline {fit['fontPx']}px, {fit['lines']} line(s))")
        finally:
            browser.close()
    for url in blocked:
        log(f"blocked network request: {url}")
    log(f"network requests blocked: {len(blocked)}")
    return written


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--formats", default=",".join(FORMAT_NAMES),
                        help=f"comma-separated subset of {', '.join(FORMAT_NAMES)}")
    args = parser.parse_args(argv)
    try:
        render(load_config(args.config), [f.strip() for f in args.formats.split(",") if f.strip()])
    except (ConfigError, HeadlineTooLong) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

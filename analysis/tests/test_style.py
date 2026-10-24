import pytest

from lib import style


@pytest.mark.parametrize("size", ["feed", "vertical"])
def test_new_figure_is_exact_pixel_size(size):
    fig, _ = style.new_figure(size)
    width, height = fig.get_size_inches() * fig.dpi
    assert (round(width), round(height)) == style.SIZES[size]
    style.plt.close(fig)


@pytest.mark.parametrize("size", ["feed", "vertical"])
def test_axes_sit_inside_the_safe_zone(size):
    fig_layout = style.layout(size)
    safe, axes = fig_layout.safe, fig_layout.axes
    assert safe.left <= axes.left < axes.right <= safe.right
    assert safe.top < axes.top < axes.bottom < fig_layout.source_center < fig_layout.footer_baseline <= safe.bottom


@pytest.mark.parametrize("size", ["feed", "vertical"])
def test_axis_labels_clear_the_footer(size):
    fig_layout = style.layout(size)
    room = fig_layout.source_center - fig_layout.axes.bottom
    assert room >= style.TEXT_PX["tick"] + style.TEXT_PX["label"] + style.TEXT_PX["source"] + 60


def test_vertical_clears_tiktok_and_reels_overlays():
    safe = style.layout("vertical").safe
    assert safe.top >= 220
    assert style.SIZES["vertical"][1] - safe.bottom >= 380
    assert style.SIZES["vertical"][0] - safe.right >= 140


def test_highlight_marks_only_the_point():
    assert style.highlight(["DAL", "PHI", "NYG"], {"PHI"}) == [style.GRAY, style.ACCENT, style.GRAY]


def ten_px_per_char(text: str) -> float:
    return len(text) * 10.0


def test_wrap_title_fits_width():
    assert style.wrap_title("Dallas is better than its record", 160, ten_px_per_char) == [
        "Dallas is better",
        "than its record",
    ]


def test_wrap_title_rejects_a_third_line():
    with pytest.raises(ValueError, match="shorten"):
        style.wrap_title("one two three four five six", 80, ten_px_per_char)


@pytest.mark.parametrize("text", ["12", "-3.5", "−7", "45%", "1,250", "+0.12"])
def test_numbers_get_the_number_font(text):
    assert style.is_number(text)


@pytest.mark.parametrize("text", ["DAL", "Week 6", "", "Run defense"])
def test_words_keep_the_body_font(text):
    assert not style.is_number(text)


def test_output_path_naming():
    assert style.output_path("dal-week06", "feed") == style.OUTPUT_DIR / "dal-week06-feed.png"


@pytest.mark.parametrize("name", ["../escape", "Dal Week", ""])
def test_output_path_rejects_unsafe_names(name):
    with pytest.raises(ValueError):
        style.output_path(name, "feed")


def test_missing_font_raises_instead_of_falling_back(monkeypatch, tmp_path):
    monkeypatch.setattr(style, "FONT_DIR", tmp_path)
    with pytest.raises(FileNotFoundError, match="BarlowCondensed-ExtraBold.ttf"):
        style.font("title")


def test_export_refuses_a_figure_of_the_other_size():
    fig, _ = style.new_figure("feed")
    with pytest.raises(ValueError):
        style.export(fig, "mismatch", "vertical")
    style.plt.close(fig)

import nbformat
import pytest

from tools import run_notebook


def notebook(tagged=True):
    params = nbformat.v4.new_code_cell('TEAM = "DAL"\nSEASON = None  # latest',
                                       metadata={"tags": ["parameters"]} if tagged else {})
    return nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell("# Title"), params,
                                           nbformat.v4.new_code_cell("print(TEAM)")])


def test_inject_adds_an_override_cell_after_the_parameters_cell():
    original = notebook()
    result = run_notebook.inject_parameters(original, {"TEAM": "PHI", "SEASON": 2026})
    assert len(result.cells) == 4
    assert result.cells[2].source == "TEAM = 'PHI'\nSEASON = 2026"
    assert result.cells[2].metadata["tags"] == ["injected-parameters"]
    assert len(original.cells) == 3


def test_inject_with_no_params_changes_nothing():
    assert len(run_notebook.inject_parameters(notebook(), {}).cells) == 3


def test_inject_refuses_unknown_parameter_names():
    with pytest.raises(run_notebook.NotebookRunError, match="not parameters of this notebook: TEMA"):
        run_notebook.inject_parameters(notebook(), {"TEMA": "PHI"})


def test_inject_refuses_a_notebook_without_a_parameters_cell():
    with pytest.raises(run_notebook.NotebookRunError, match="tagged 'parameters'"):
        run_notebook.inject_parameters(notebook(tagged=False), {"TEAM": "PHI"})


@pytest.mark.parametrize(
    ("text", "expected"),
    [("TEAM=PHI", ("TEAM", "PHI")), ("SEASON=2026", ("SEASON", 2026)), ("SEASON=None", ("SEASON", None)),
     ('TEAM="DAL"', ("TEAM", "DAL"))],
)
def test_parse_param(text, expected):
    assert run_notebook.parse_param(text) == expected


@pytest.mark.parametrize("text", ["TEAM", "=PHI", "not a name=1"])
def test_parse_param_refuses_malformed_text(text):
    with pytest.raises(run_notebook.NotebookRunError):
        run_notebook.parse_param(text)

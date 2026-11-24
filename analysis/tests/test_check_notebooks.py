import json

import pytest

from tools import check_notebooks as check


def notebook(*cells: dict) -> dict:
    return {"cells": list(cells), "metadata": {}, "nbformat": 4, "nbformat_minor": 5}


def code(source: str, outputs: list | None = None, count: int | None = None) -> dict:
    return {"cell_type": "code", "source": source, "outputs": outputs or [], "execution_count": count,
            "metadata": {}}


def test_clean_notebook_passes():
    assert check.problems(notebook(code("TEAM = 'DAL'"), {"cell_type": "markdown", "source": "# Q"}), "nb") == []


def test_outputs_and_counts_are_flagged():
    found = check.problems(notebook(code("1 + 1", [{"output_type": "execute_result", "data": {}}], 3)), "nb")
    assert any("has outputs" in p for p in found)
    assert any("execution count" in p for p in found)


@pytest.mark.parametrize(
    "source",
    [
        "url = 'postgresql+psycopg://user:pw@host/db'",
        "DATABASE_URL = 'x'",
        # Assembled at runtime so no key-shaped literal trips GitHub push
        # protection or the CI gitleaks scan.
        "key = '" + "0123456789abcdef" * 2 + "'",
        "token = '" + "a1B2c3D4e5" * 4 + "'",
    ],
)
def test_secret_shapes_are_flagged(source):
    assert check.problems(notebook(code(source)), "nb")


def test_secrets_in_outputs_are_flagged():
    printed = [{"output_type": "stream", "text": ["postgres://u:p@h/d\n"]}]
    found = check.problems(notebook(code("print(url)", printed)), "nb")
    assert any("connection string" in p for p in found)


@pytest.mark.parametrize("source", ["read_engine()", "points_per_play_over_the_last_four_weeks = 1"])
def test_ordinary_code_is_not_a_secret(source):
    assert check.problems(notebook(code(source)), "nb") == []


def test_main_fails_on_a_dirty_notebook_and_skips_checkpoints(tmp_path, capsys):
    (tmp_path / "clean.ipynb").write_text(json.dumps(notebook(code("x = 1"))))
    checkpoints = tmp_path / ".ipynb_checkpoints"
    checkpoints.mkdir()
    (checkpoints / "clean-checkpoint.ipynb").write_text(json.dumps(notebook(code("x", [{"text": "1"}], 1))))
    assert check.main([str(tmp_path)]) == 0

    (tmp_path / "dirty.ipynb").write_text(json.dumps(notebook(code("x", [{"text": "1"}], 1))))
    assert check.main([str(tmp_path)]) == 1
    assert "dirty.ipynb cell 1" in capsys.readouterr().out

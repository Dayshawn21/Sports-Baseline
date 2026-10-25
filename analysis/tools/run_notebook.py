"""Run a notebook top to bottom on a clean kernel, with parameters, without touching the saved file.

    analysis/.venv/Scripts/python analysis/tools/run_notebook.py analysis/week01-save-the-season.ipynb --param TEAM=PHI
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import copy
import sys
from pathlib import Path

import nbformat
from jupyter_client.kernelspec import NoSuchKernel
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

PARAMETERS_TAG = "parameters"
KERNEL_INSTALL = ('analysis/.venv/Scripts/python -m ipykernel install --user --name nbtg '
                  '--display-name "Numbers Behind the Game"')


class NotebookRunError(RuntimeError):
    pass


def parse_param(text: str) -> tuple[str, object]:
    """NAME=value; the value is a Python literal when it parses as one (None, 7, "x"), else a string."""
    name, sep, raw = text.partition("=")
    if not sep or not name.isidentifier():
        raise NotebookRunError(f"parameters look like NAME=value, got {text!r}")
    try:
        value = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        value = raw
    return name, value


def _parameters_index(notebook: nbformat.NotebookNode) -> int:
    for index, cell in enumerate(notebook.cells):
        if cell.cell_type == "code" and PARAMETERS_TAG in cell.get("metadata", {}).get("tags", []):
            return index
    raise NotebookRunError(f"no code cell is tagged {PARAMETERS_TAG!r}")


def _assigned_names(source: str) -> set[str]:
    return {target.id for node in ast.parse(source).body if isinstance(node, ast.Assign)
            for target in node.targets if isinstance(target, ast.Name)}


def inject_parameters(notebook: nbformat.NotebookNode, params: dict[str, object]) -> nbformat.NotebookNode:
    """A copy with a cell after the parameters cell that overrides them; unknown names are refused."""
    result = copy.deepcopy(notebook)
    index = _parameters_index(result)
    unknown = set(params) - _assigned_names(result.cells[index].source)
    if unknown:
        raise NotebookRunError(f"not parameters of this notebook: {', '.join(sorted(unknown))}")
    if params:
        source = "\n".join(f"{name} = {value!r}" for name, value in params.items())
        result.cells.insert(index + 1, nbformat.v4.new_code_cell(source, metadata={"tags": ["injected-parameters"]}))
    return result


def run(path: Path, params: dict[str, object]) -> nbformat.NotebookNode:
    notebook = inject_parameters(nbformat.read(path, as_version=4), params)
    kernel = notebook.metadata.get("kernelspec", {}).get("name", "python3")
    client = NotebookClient(notebook, kernel_name=kernel, timeout=600,
                            resources={"metadata": {"path": str(path.parent)}})
    try:
        client.execute()
    except NoSuchKernel as error:
        raise NotebookRunError(f"kernel {kernel!r} is not installed; run once: {KERNEL_INSTALL}") from error
    except CellExecutionError as error:
        raise NotebookRunError(str(error)) from error
    return notebook


def main(argv: list[str]) -> int:
    if sys.platform == "win32":
        # zmq needs a selector loop; Windows defaults to Proactor and warns on every run.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("notebook", type=Path)
    parser.add_argument("--param", action="append", default=[], metavar="NAME=value")
    args = parser.parse_args(argv)
    try:
        params = dict(parse_param(p) for p in args.param)
        notebook = run(args.notebook.resolve(), params)
    except NotebookRunError as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1
    print(f"ran {sum(c.cell_type == 'code' for c in notebook.cells)} code cells in {args.notebook.name} with {params}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

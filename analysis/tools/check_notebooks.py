"""Fail if a notebook carries outputs, execution counts or anything shaped like a secret.

Run from the repo root before committing:
    analysis/.venv/Scripts/python analysis/tools/check_notebooks.py [paths...]
"""
from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path

ANALYSIS_DIR = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".ipynb_checkpoints", ".venv"}

SECRET_PATTERNS = {
    "a connection string": re.compile(r"postgres(?:ql)?(?:\+\w+)?://", re.IGNORECASE),
    "a DATABASE_URL assignment": re.compile(r"DATABASE_URL\s*="),
    "a hex key": re.compile(r"\b[0-9a-fA-F]{32,}\b"),
    # Letters and digits mixed over 32+ characters: API keys and tokens, not words.
    "a key-shaped token": re.compile(r"\b(?=[A-Za-z0-9+/_-]*\d)(?=[A-Za-z0-9+/_-]*[A-Za-z])[A-Za-z0-9+/_-]{32,}\b"),
}


def _text(value: str | list[str]) -> str:
    return value if isinstance(value, str) else "".join(value)


def _output_text(outputs: list[dict]) -> str:
    parts = []
    for output in outputs:
        parts.append(_text(output.get("text", "")))
        for data in output.get("data", {}).values():
            if isinstance(data, (str, list)):
                parts.append(_text(data))
    return "\n".join(parts)


def problems(notebook: dict, name: str) -> list[str]:
    found = []
    for number, cell in enumerate(notebook.get("cells", []), start=1):
        where = f"{name} cell {number}"
        outputs = cell.get("outputs", [])
        if outputs:
            found.append(f"{where}: has outputs; clear them before committing")
        if cell.get("execution_count") is not None:
            found.append(f"{where}: has an execution count; clear outputs before committing")
        text = _text(cell.get("source", "")) + "\n" + _output_text(outputs)
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                found.append(f"{where}: contains {label}")
    return found


def notebook_paths(paths: Iterable[str]) -> list[Path]:
    given = [Path(p) for p in paths] or [ANALYSIS_DIR]
    found: list[Path] = []
    for path in given:
        candidates = [path] if path.is_file() else sorted(path.rglob("*.ipynb"))
        found += [c for c in candidates if not SKIP_PARTS.intersection(c.parts)]
    return found


def main(argv: list[str]) -> int:
    report = []
    paths = notebook_paths(argv)
    for path in paths:
        report += problems(json.loads(path.read_text(encoding="utf-8")), str(path))
    for line in report:
        print(line)
    print(f"{len(paths)} notebook(s) checked, {len(report)} problem(s)")
    return 1 if report else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

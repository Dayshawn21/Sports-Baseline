"""The hosted API installs requirements-api.txt, which leaves out scikit-learn.

LightGBM imports scikit-learn whenever it is installed, about 49 MB of the
512 MB instance, and nothing on the request path uses it. These tests keep it
that way: a request-path import fails here instead of on the next deploy.
"""
import re
import subprocess
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]


def _packages(path: Path) -> set[str]:
    names: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith(("#", "-r")):
            names.add(re.split(r"[\[=<>~!]", line, maxsplit=1)[0].lower())
    return names


def test_the_hosted_install_leaves_out_scikit_learn_and_pytest():
    hosted = _packages(API_DIR / "requirements-api.txt")

    assert "scikit-learn" not in hosted
    assert "pytest" not in hosted
    assert {"fastapi", "lightgbm", "joblib", "pandas"} <= hosted


def test_the_full_install_is_the_hosted_one_plus_the_extras():
    text = (API_DIR / "requirements.txt").read_text(encoding="utf-8")

    assert "-r requirements-api.txt" in text.splitlines()
    assert _packages(API_DIR / "requirements.txt") == {"scikit-learn", "pytest"}


def test_no_model_bundle_needs_scikit_learn_to_load():
    # ModelRegistry joblib-loads a calibration beside its model, and unpickling
    # one imports scikit-learn. Adding one means moving scikit-learn back.
    assert sorted(p.name for p in (API_DIR / "models").glob("*_calibration.joblib")) == []


def test_the_app_starts_without_scikit_learn():
    code = "import sys; sys.modules['sklearn'] = None; import app.main"

    result = subprocess.run(
        [sys.executable, "-c", code], cwd=API_DIR, capture_output=True, text=True, timeout=120,
    )

    assert result.returncode == 0, result.stderr[-2000:]

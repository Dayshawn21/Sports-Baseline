from decimal import Decimal

import pytest

from app.core.prop_probs import normal_cdf
from app.core.prop_projection import opt_float


@pytest.mark.parametrize(
    ("z", "expected"),
    [(0.0, 0.5), (1.0, 0.8413447460685429), (-1.0, 0.15865525393145707), (1.96, 0.9750021048517795)],
)
def test_normal_cdf(z: float, expected: float) -> None:
    assert normal_cdf(z) == pytest.approx(expected, abs=1e-12)


def test_normal_cdf_is_symmetric() -> None:
    assert normal_cdf(0.7) + normal_cdf(-0.7) == pytest.approx(1.0)


@pytest.mark.parametrize(("value", "expected"), [(None, None), (Decimal("1.25"), 1.25), (3, 3.0), (0, 0.0)])
def test_opt_float(value: Decimal | int | None, expected: float | None) -> None:
    result = opt_float(value)
    assert result == expected
    assert result is None or type(result) is float

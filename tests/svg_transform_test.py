import pytest
from math import degrees, pi
from nanosvg.svg_transform import *
from typing import Tuple


def _round(transform: Transform, digits=2):
    return Transform(*(round(v, digits) for v in transform))

@pytest.mark.parametrize(
    "transform, expected_result",
    [
        # translate(tx)
        (
            'translate(-5)',
            Transform(1, 0, 0, 1, -5, 0)
        ),
        # translate(tx ty)
        (
            'translate(3.5, -0.65)',
            Transform(1, 0, 0, 1, 3.5, -0.65)
        ),
        # scale(sx)
        (
            'scale(2)',
            Transform(2, 0, 0, 2, 0, 0)
        ),
        # scale(sx,sy)
        (
            'scale(-2 -3)',
            Transform(-2, 0, 0, -3, 0, 0)
        ),
        # rotate(angle)
        (
            f'rotate({degrees(pi / 4)})',
            Transform(0.707, 0.707, -0.707, 0.707, 0, 0)
        ),
        # rotate(angle cx cy)
        (
            f'rotate({degrees(pi / 2)}, 5, 6)',
            Transform(0, 1, -1, 0, 11, 1)
        ),
        # skewX(angle)
        (
            f'skewx({degrees(pi / 8)})',
            Transform(1, 0, 0.414, 1, 0, 0)
        ),
        # skewY(angle)
        (
            f'skewY({degrees(pi / 8)})',
            Transform(1, 0.414, 0, 1, 0, 0)
        ),
        # example from FontTools
        (
            'matrix(2, 0, 0, 3, 1, 6) matrix(4, 3, 2, 1, 5, 6)',
            Transform(8, 9, 4, 3, 11, 24)
        ),
        # svg spec example
        # 255 decimal expected part changed from 03 to 061
        (
            'translate(50 90),rotate(-45) translate(130,160)',
            Transform(0.707, -0.707, 0.707, 0.707, 255.061, 111.213)
        ),
    ],
)
def test_parse_svg_transform(transform: str, expected_result: Tuple[str, ...]):
    actual = _round(parse_svg_transform(transform), 3)
    print(f"A: {actual}")
    print(f"E: {expected_result}")
    assert actual == expected_result


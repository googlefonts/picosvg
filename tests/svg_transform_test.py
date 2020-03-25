import pytest
import math
from nanosvg.svg_transform import *
from typing import Tuple


def _round(transform: Transform, digits=2):
    return Transform(*(round(v, digits) for v in transform.tuple()))

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
            f'rotate({math.pi / 4})',
            Transform(0.707, 0.707, -0.707, 0.707, 0, 0)
        ),
        # rotate(angle cx cy)
        (
            f'rotate({math.pi / 2}, 5, 6)',
            Transform(0, 1, -1, 0, 11, 1)
        ),
        # skewX(angle)
        (
            f'skewx({math.pi / 8})',
            Transform(1, 0, 0.414, 1, 0, 0)
        ),
        # skewY(angle)
        (
            f'skewY({math.pi / 8})',
            Transform(1, 0.414, 0, 1, 0, 0)
        ),
        # example from FontTools
        (
            'matrix(2, 0, 0, 3, 1, 6) matrix(4, 3, 2, 1, 5, 6)',
            Transform(8, 9, 4, 3, 11, 24)
        ),
        # a list slightly modified from svg spec example
        # answer differs from that example but agrees with FontTools
        (
            'translate(50 90),rotate(-45) translate(130,160)',
            Transform(0.525, -0.851, 0.851, 0.525, 254.436, 63.434)
        ),
    ],
)
def test_parse_svg_transform(transform: str, expected_result: Tuple[str, ...]):
    actual = _round(parse_svg_transform(transform), 3)
    print(f"A: {actual}")
    print(f"E: {expected_result}")
    assert actual == expected_result


from picosvg.svg_path_iter import parse_svg_path
import pytest


@pytest.mark.parametrize(
    "d, expected",
    [
        ("M0,0", (("M", (0, 0)),)),
        (
            "M0 0 1,2 3, 4 C5, 6-7.0.5 8-9Z",
            (("M", (0, 0, 1, 2, 3, 4)), ("C", (5, 6, -7.0, 0.5, 8, -9)), ("Z", ())),
        ),
        ("A3.996 3.996 0 0016 9", (("A", (3.996, 3.996, 0, 0, 0, 16, 9)),)),
        (
            "a.1.2.3,10-.4-.5.6.7.8e+2,01.9+.1e-2",
            (
                (
                    "a",
                    (
                        0.1,
                        0.2,
                        0.3,
                        1,
                        0,
                        -0.4,
                        -0.5,
                        0.6,
                        0.7,
                        80.0,
                        0,
                        1,
                        0.9,
                        0.001,
                    ),
                ),
            ),
        ),
        # TODO(anthrotype) add more tests
    ],
)
def test_parse_svg_path(d, expected):
    assert tuple(parse_svg_path(d, exploded=False)) == expected

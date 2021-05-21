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
        # real-world test case from https://github.com/googlefonts/picosvg/issues/171
        (
            "M448.6 997.7c.2 5.6 16.6 9.4 36.5 8.4s35.8-6.2 35.5-11.8"
            "a1.7 1.7 0 00-.1-.7c-1.5-5.2-17.3-8.6-36.4-7.7s-34.4 5.8-35.5 11.1z",
            (
                ("M", (448.6, 997.7)),
                ("c", (0.2, 5.6, 16.6, 9.4, 36.5, 8.4)),
                ("s", (35.8, -6.2, 35.5, -11.8)),
                ("a", (1.7, 1.7, 0.0, 0, 0, -0.1, -0.7)),
                ("c", (-1.5, -5.2, -17.3, -8.6, -36.4, -7.7)),
                ("s", (-34.4, 5.8, -35.5, 11.1)),
                ("z", ()),
            ),
        )
        # TODO(anthrotype) add more tests
    ],
)
def test_parse_svg_path(d, expected):
    assert tuple(parse_svg_path(d, exploded=False)) == expected

# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
from picosvg.svg_transform import Affine2D
from picosvg.svg_types import SVGPath, SVGRect, Rect
from svg_test_helpers import *


@pytest.mark.parametrize(
    "path, expected_result",
    [
        # path explodes to show implicit commands & becomes absolute
        ("m1,1 2,0 1,3", "M1,1 L3,1 L4,4"),
        # Vertical, Horizontal movement
        ("m2,2 h2 v2 h-1 v-1 H8 V8", "M2,2 H4 V4 H3 V3 H8 V8"),
        # Quadratic bezier curve
        ("m2,2 q1,1 2,2 Q5,5 6,6", "M2,2 Q3,3 4,4 Q5,5 6,6"),
        # Elliptic arc
        ("m2,2 a1,1 0 0 0 3,3 A2,2 1 1 1 4,4", "M2,2 A1 1 0 0 0 5,5 A2 2 1 1 1 4,4"),
        # Cubic bezier
        ("m2,2 c1,-1 2,4 3,3 C4 4 5 5 6 6", "M2,2 C3,1 4,6 5,5 C4,4 5,5 6,6"),
        # Elliptic arc that goes haywire when stroked
        ("M7,5 a3,1 0,0,0 0,-3 a3,3 0 0 1 -4,2", "M7,5 A3 1 0 0 0 7,2 A3 3 0 0 1 3,4"),
        # clock hand's path in which the last point must be == start point when absolutized
        (
            "m63.8 63.98h0.4c2.1 0 3.8-1.7 3.8-3.8v-32.4c0-2.1-1.7-3.8-3.8-3.8h-0.4"
            "c-2.1 0-3.8 1.7-3.8 3.8v32.4c0 2.1 1.7 3.8 3.8 3.8z",
            "M63.8,63.98 H64.2 C66.3,63.98 68,62.28 68,60.18 V27.78 "
            "C68,25.68 66.3,23.98 64.2,23.98 H63.8 C61.7,23.98 60,25.68 60,27.78 "
            "V60.18 C60,62.28 61.7,63.98 63.8,63.98 Z",
        ),
        # Relative 'm' in sub-path following a closed sub-path.
        # Confirms z updates currend position correctly.
        # https://github.com/googlefonts/picosvg/issues/70
        (
            "m0,0 l0,10 l10,0 z m10,10 l0,10 l10,0 z",
            "M0,0 L0,10 L10,10 Z M10,10 L10,20 L20,20 Z",
        ),
        # Further adventures of z; it's a single backref not a stack
        (
            "M3,3 M1,1 l0,10 l4,0 z Z z l8,2 0,2 z m4,4 1,1 -2,0 z",
            "M3,3 M1,1 L1,11 L5,11 Z Z Z L9,3 L9,5 Z M5,5 L6,6 L4,6 Z",
        ),
        # Points very near subpath origin should collapse to that origin, test 1
        # Make sure to test a command with only a single coordinate (h)
        (
            "M0,0 L0,5 L5,5 L1e-10,0 Z l5,-1 0,1 H-1e-9 z",
            "M0,0 L0,5 L5,5 L0,0 Z L5,-1 L5,0 L0,0 Z",
        ),
    ],
)
def test_path_absolute(path: str, expected_result: str):
    actual = SVGPath(d=path).absolute(inplace=True).round_floats(3, inplace=True).d
    print(f"A: {actual}")
    print(f"E: {expected_result}")
    assert actual == expected_result


@pytest.mark.parametrize(
    "path, move, expected_result",
    [
        # path with implicit relative lines
        ("m1,1 2,0 1,3", (2, 2), "M3,3 l2,0 l1,3"),
        # path with implicit absolute lines
        ("M1,1 2,0 1,3", (2, 2), "M3,3 L4,2 L3,5"),
        # Vertical, Horizontal movement
        ("m2,2 h2 v2 h-1 v-1 H8 V8", (-1, -2), "M1,0 h2 v2 h-1 v-1 H7 V6"),
        # Quadratic bezier curve
        ("m2,2 q1,1 2,2 Q5,5 6,6", (3, 1), "M5,3 q1,1 2,2 Q8,6 9,7"),
        # Elliptic arc
        (
            "m2,2 a1,1 0 0 0 3,3 A2,2 1 1 1 4,4",
            (1, 3),
            "M3,5 a1 1 0 0 0 3,3 A2 2 1 1 1 5,7",
        ),
        # Cubic bezier
        ("m2,2 c1,-1 2,4 3,3 C4 4 5 5 6 6", (4, 2), "M6,4 c1,-1 2,4 3,3 C8,6 9,7 10,8"),
    ],
)
def test_path_move(path: str, move, expected_result: str):
    actual = SVGPath(d=path).move(*move, inplace=True).d
    print(f"A: {actual}")
    print(f"E: {expected_result}")
    assert actual == expected_result


@pytest.mark.parametrize(
    "path, expected_result",
    [
        # C/S
        (
            "M600,800 C625,700 725,700 750,800 S875,900 900,800",
            "M600,800 C625,700 725,700 750,800 C775,900 875,900 900,800",
        ),
        # Q/T
        (
            "M16,12 Q20,14 16,16 T16,20 L24,20 24,12",
            "M16,12 Q20,14 16,16 Q12,18 16,20 L24,20 L24,12",
        ),
        # S without preceding C
        ("S875,900 900,800", "C0,0 875,900 900,800"),
        # T without preceding Q
        ("M16,12 T16,20", "M16,12 Q16,12 16,20"),
        # C/s
        (
            "M600,800 C625,700 725,700 750,800 s55,55 200,100",
            "M600,800 C625,700 725,700 750,800 C775,900 805,855 950,900",
        ),
        # https://github.com/rsheeter/playground/issues/4
        (
            "m34 23.25c14.68 0 26.62 18.39 26.62 41s-11.94 41-26.62 41-26.62-18.39-26.62-41 11.94-41 26.62-41z",
            "M34,23.25 c14.68,0 26.62,18.39 26.62,41 C60.62,86.86 48.68,105.25 34,105.25 C19.32,105.25 7.38,86.86 7.38,64.25 C7.38,41.64 19.32,23.25 34,23.25 z",
        ),
    ],
)
def test_expand_shorthand(path, expected_result):
    actual = (
        SVGPath(d=path).expand_shorthand(inplace=True).round_floats(3, inplace=True).d
    )
    print(f"A: {actual}")
    print(f"E: {expected_result}")
    assert actual == expected_result


@pytest.mark.parametrize(
    "shape, expected_bbox",
    [
        # plain rect
        ('<rect x="2" y="2" width="6" height="2" />', Rect(2, 2, 6, 2)),
        # triangle
        ('<path d="m5,2 2.5,5 -5,0 z" />', Rect(2.5, 2, 5, 5)),
    ],
)
def test_bounding_box(shape, expected_bbox):
    nsvg = svg(shape)
    actual_bbox = nsvg.shapes()[0].bounding_box()
    print(f"A: {actual_bbox}")
    print(f"E: {expected_bbox}")
    assert actual_bbox == expected_bbox


@pytest.mark.parametrize(
    "path, expected_result",
    [
        (
            "M-1,0 A1,1 0,0,0 1,0 z",
            "M-1,0 C-1,0.552 -0.552,1 0,1 C0.552,1 1,0.552 1,0 z",
        ),
        # relative coordinates
        (
            "M-1,0 a1,1 0,0,0 2,0 z",
            "M-1,0 C-1,0.552 -0.552,1 0,1 C0.552,1 1,0.552 1,0 z",
        ),
        # degenerate arcs as straight lines
        ("M-1,0 A0,1 0,0,0 0,1 A1,0 0,0,0 1,0 z", "M-1,0 L0,1 L1,0 z"),
        # two arcs closing on each other in a circle; last point == first
        (
            "M4,64 A60 60 0 1 1 124,64 A60 60 0 1 1 4,64 z",
            "M4,64 C4,30.863 30.863,4 64,4 C97.137,4 124,30.863 124,64 "
            "C124,97.137 97.137,124 64,124 C30.863,124 4,97.137 4,64 z",
        ),
    ],
)
def test_arcs_to_cubics(path, expected_result):
    actual = (
        SVGPath(d=path).arcs_to_cubics(inplace=True).round_floats(3, inplace=True).d
    )
    print(f"A: {actual}")
    print(f"E: {expected_result}")
    assert actual == expected_result


@pytest.mark.parametrize(
    "path, transform, expected_result",
    [
        # translate
        (
            "M1,1 L2,1 L2,2 L1,2 Z",
            Affine2D.identity().translate(2, 1),
            "M3,2 L4,2 L4,3 L3,3 Z",
        ),
        # same shape as above under a degenerate transform
        ("M1,1 L2,1 L2,2 L1,2 Z", Affine2D.degenerate(), "M0,0"),
    ],
)
def test_apply_basic_transform(path, transform, expected_result):
    actual = SVGPath(d=path).apply_transform(transform).round_floats(3).d
    print(f"A: {actual}")
    print(f"E: {expected_result}")
    assert actual == expected_result


@pytest.mark.parametrize(
    "path, expected_result",
    [
        (SVGRect(width=1, height=1), True),
        # we see paths with move and nothing else in the wild
        (SVGPath(d="M1,2"), False),
        (SVGPath(d="M1,2 M3,4"), False),
        # a straight line with only a fill (no stroke) and no area does not paint
        (SVGPath(d="M1,2 L3,4 Z"), False),
        # a straight line with a stroke does paint
        (SVGPath(d="M1,2 L3,4", stroke="black"), True),
        # a stroke with 0 width doesn't paint
        (
            SVGPath(d="M1,2 L3,4 L3,1 Z", fill="none", stroke="black", stroke_width=0),
            False,
        ),
        # a filled triangle does paint (no matter the invisible stroke)
        (
            SVGPath(d="M1,2 L3,4 L3,1 Z", fill="red", stroke="black", stroke_width=0),
            True,
        ),
        # we're explicitly told not to display, so we don't
        (SVGPath(d="M1,1 L2,1 L2,2 L1,2 Z", display="none"), False),
        (SVGPath(style="display:none;fill:#F5FAFC;", d="M1,1 L2,1 L2,2 L1,2 Z"), False),
    ],
)
def test_might_paint(path, expected_result):
    assert path.might_paint() == expected_result, path


@pytest.mark.parametrize(
    "shape, expected",
    [
        (
            SVGRect(width=10, height=10, style="fill:red;opacity:0.5;"),
            SVGRect(width=10, height=10, fill="red", opacity=0.5),
        ),
        (
            SVGPath(
                d="M0,0 L10,0 L10,10 L0,10 Z",
                style="stroke:blue;stroke-opacity:0.8;filter:url(#x);",
            ),
            SVGPath(
                d="M0,0 L10,0 L10,10 L0,10 Z",
                stroke="blue",
                stroke_opacity=0.8,
                style="filter:url(#x);",
            ),
        ),
    ],
)
def test_apply_style_attribute(shape, expected):
    actual = shape.apply_style_attribute()
    assert actual == expected
    assert shape.apply_style_attribute(inplace=True) == expected


@pytest.mark.parametrize(
    "path, multiple_of, expected_result",
    [
        ("m1,1 2,0 1,3", 0.1, "m1,1 2,0 1,3"),
        # why a multiple that divides evenly into 1 is a good idea
        ("m1,1 2,0 1,3", 0.128, "m1.024,1.024 2.048,0 1.024,2.944"),
    ],
)
def test_round_multiple(path: str, multiple_of: float, expected_result: str):
    actual = SVGPath(d=path).round_multiple(multiple_of, inplace=True).d
    print(f"A: {actual}")
    print(f"E: {expected_result}")
    assert actual == expected_result


@pytest.mark.parametrize(
    "shape, expected",
    [
        # neither fill nor stroke, unchanged
        (
            SVGPath(d="m1,1 2,0 1,3 z", fill="none", fill_opacity=0.0),
            SVGPath(d="m1,1 2,0 1,3 z", fill="none", fill_opacity=0.0),
        ),
        # both fill and stroke, also unchanged
        (
            SVGPath(
                d="m1,1 2,0 1,3 z",
                fill="red",
                fill_opacity=0.5,
                stroke="black",
                stroke_opacity=0.8,
                opacity=0.9,
            ),
            SVGPath(
                d="m1,1 2,0 1,3 z",
                fill="red",
                fill_opacity=0.5,
                stroke="black",
                stroke_opacity=0.8,
                opacity=0.9,
            ),
        ),
        # no stroke, only fill: merge and drop fill_opacity
        (
            SVGPath(
                d="m1,1 2,0 1,3 z",
                fill="red",
                fill_opacity=0.5,
                opacity=0.9,
            ),
            SVGPath(
                d="m1,1 2,0 1,3 z",
                fill="red",
                opacity=0.45,  # 0.9 * 0.5
            ),
        ),
        # no fill, only stroke: merge and drop stroke_opacity
        (
            SVGPath(
                d="m1,1 2,0 1,3 z",
                fill="none",
                stroke="black",
                stroke_opacity=0.3,
                opacity=0.9,
            ),
            SVGPath(
                d="m1,1 2,0 1,3 z",
                fill="none",
                stroke="black",
                opacity=0.27,  # 0.9 * 0.3
            ),
        ),
    ],
)
def test_normalize_opacity(shape, expected):
    assert shape.normalize_opacity() == expected

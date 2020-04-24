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
from picosvg.svg_types import SVGPath, Rect
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
    ],
)
def test_path_absolute(path: str, expected_result: str):
    actual = SVGPath(d=path).absolute(inplace=True).d
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
    actual = SVGPath(d=path).expand_shorthand(inplace=True).d
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
    ],
)
def test_arcs_to_cubics(path, expected_result):
    actual = SVGPath(d=path).arcs_to_cubics(inplace=True).d
    print(f"A: {actual}")
    print(f"E: {expected_result}")
    assert actual == expected_result

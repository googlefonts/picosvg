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
from picosvg import svg_pathops
from picosvg.svg_types import SVGCircle, SVGPath, SVGRect


_TEST_TOLERENCE = 0.25  # what Skia typically uses


def _round(pt, digits):
    return tuple(round(v, digits) for v in pt)


@pytest.mark.parametrize(
    "shape, tolerance, expected_segments, expected_path",
    [
        # path
        (
            SVGPath(d="M1,1 2,2 z"),
            _TEST_TOLERENCE,
            (("moveTo", ((1.0, 1.0),)), ("lineTo", ((2.0, 2.0),)), ("closePath", ())),
            "M1,1 L2,2 Z",
        ),
        # rect
        (
            SVGRect(x=4, y=4, width=6, height=16),
            _TEST_TOLERENCE,
            (
                ("moveTo", ((4.0, 4.0),)),
                ("lineTo", ((10.0, 4.0),)),
                ("lineTo", ((10.0, 20.0),)),
                ("lineTo", ((4.0, 20.0),)),
                ("lineTo", ((4.0, 4.0),)),
                ("closePath", ()),
            ),
            "M4,4 L10,4 L10,20 L4,20 L4,4 Z",
        ),
        # https://github.com/rsheeter/picosvg/issues/1
        # intolerance makes for poor circles
        (
            SVGCircle(cx=5, cy=5, r=4),
            _TEST_TOLERENCE,
            (
                ("moveTo", ((1.0, 5.0),)),
                (
                    "qCurveTo",
                    ((1.0, 1.0), (9.0, 1.0), (9.0, 9.0), (1.0, 9.0), (1.0, 5.0)),
                ),
                ("closePath", ()),
            ),
            "M1,5 Q1,1 5,1 Q9,1 9,5 Q9,9 5,9 Q1,9 1,5 Z",
        ),
        # https://github.com/rsheeter/picosvg/issues/1
        # a more tolerent circle
        (
            SVGCircle(cx=5, cy=5, r=4),
            0.02,  # 0.1% error when drawn on a 20x20 vbox
            (
                ("moveTo", ((1.0, 5.0),)),
                (
                    "qCurveTo",
                    (
                        (1.0, 4.204),
                        (1.609, 2.734),
                        (2.734, 1.609),
                        (4.204, 1.0),
                        (5.796, 1.0),
                        (7.266, 1.609),
                        (8.391, 2.734),
                        (9.0, 4.204),
                        (9.0, 5.796),
                        (8.391, 7.266),
                        (7.266, 8.391),
                        (5.796, 9.0),
                        (4.204, 9.0),
                        (2.734, 8.391),
                        (1.609, 7.266),
                        (1.0, 5.796),
                        (1.0, 5.0),
                    ),
                ),
                ("closePath", ()),
            ),
            "M1,5 Q1,4.204 1.304,3.469 Q1.609,2.734 2.172,2.172 Q2.734,1.609 3.469,1.304 Q4.204,1 5,1 Q5.796,1 6.531,1.304 Q7.266,1.609 7.828,2.172 Q8.391,2.734 8.696,3.469 Q9,4.204 9,5 Q9,5.796 8.696,6.531 Q8.391,7.266 7.828,7.828 Q7.266,8.391 6.531,8.696 Q5.796,9 5,9 Q4.204,9 3.469,8.696 Q2.734,8.391 2.172,7.828 Q1.609,7.266 1.304,6.531 Q1,5.796 1,5 Z",
        ),
    ],
)
def test_skia_path_roundtrip(shape, tolerance, expected_segments, expected_path):
    skia_path = svg_pathops.skia_path(shape, tolerance)
    rounded_segments = list(skia_path.segments)
    for idx, (cmd, points) in enumerate(rounded_segments):
        rounded_segments[idx] = (cmd, tuple(_round(pt, 3) for pt in points))
    assert tuple(rounded_segments) == expected_segments
    assert svg_pathops.svg_path(skia_path).d == expected_path


@pytest.mark.parametrize(
    "shapes, expected_result",
    [
        # rect's
        (
            (
                SVGRect(x=4, y=4, width=6, height=6),
                SVGRect(x=6, y=6, width=6, height=6),
            ),
            "M4,4 L10,4 L10,6 L12,6 L12,12 L6,12 L6,10 L4,10 Z",
        ),
    ],
)
def test_pathops_union(shapes, expected_result):
    assert svg_pathops.union(_TEST_TOLERENCE, *shapes).d == expected_result


@pytest.mark.parametrize(
    "shapes, expected_result",
    [
        # rect's
        (
            (
                SVGRect(x=4, y=4, width=6, height=6),
                SVGRect(x=6, y=6, width=6, height=6),
            ),
            "M6,6 L10,6 L10,10 L6,10 Z",
        ),
    ],
)
def test_pathops_intersection(shapes, expected_result):
    assert svg_pathops.intersection(_TEST_TOLERENCE, *shapes).d == expected_result

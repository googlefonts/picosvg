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


def _round(pt, digits):
    return tuple(round(v, digits) for v in pt)


@pytest.mark.parametrize(
    "shape, expected_segments, expected_path",
    [
        # path
        (
            SVGPath(d="M1,1 2,2 z"),
            (("moveTo", ((1.0, 1.0),)), ("lineTo", ((2.0, 2.0),)), ("closePath", ())),
            "M1,1 L2,2 Z",
        ),
        # rect
        (
            SVGRect(x=4, y=4, width=6, height=16),
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
        (
            SVGCircle(cx=5, cy=5, r=4),
            (
                ("moveTo", ((9.0, 5.0),)),
                ("curveTo", ((9.0, 7.2091), (7.2091, 9.0), (5.0, 9.0))),
                ("curveTo", ((2.7909, 9.0), (1.0, 7.2091), (1.0, 5.0))),
                ("curveTo", ((1.0, 2.7909), (2.7909, 1.0), (5.0, 1.0))),
                ("curveTo", ((7.2091, 1.0), (9.0, 2.7909), (9.0, 5.0))),
                ("closePath", ()),
            ),
            "M9,5 C9,7.2091 7.2091,9 5,9 C2.7909,9 1,7.2091 1,5 C1,2.7909 2.7909,1 5,1 C7.2091,1 9,2.7909 9,5 Z",
        ),
        # TODO: round-trip SVGPath with fill_rule="evenodd"
    ],
)
def test_skia_path_roundtrip(shape, expected_segments, expected_path):
    # We round to 4 decimal places to confirm custom value works
    skia_path = svg_pathops.skia_path(shape.as_cmd_seq(), shape.fill_rule)
    rounded_segments = list(skia_path.segments)
    for idx, (cmd, points) in enumerate(rounded_segments):
        rounded_segments[idx] = (cmd, tuple(_round(pt, 4) for pt in points))
    assert tuple(rounded_segments) == expected_segments
    assert (
        SVGPath.from_commands(svg_pathops.svg_commands(skia_path))
        .round_floats(4, inplace=True)
        .d
        == expected_path
    )


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
        )
    ],
)
def test_pathops_union(shapes, expected_result):
    assert (
        SVGPath.from_commands(
            svg_pathops.union(
                [s.as_cmd_seq() for s in shapes], [s.clip_rule for s in shapes]
            )
        ).d
        == expected_result
    )


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
        )
    ],
)
def test_pathops_intersection(shapes, expected_result):
    assert (
        SVGPath.from_commands(
            svg_pathops.intersection(
                [s.as_cmd_seq() for s in shapes], [s.clip_rule for s in shapes]
            )
        ).d
        == expected_result
    )


@pytest.mark.parametrize(
    "shape, expected_result",
    [
        # rectangles with no width or height have zero area
        (SVGRect(x=1, y=1, width=0, height=1), 0.0),
        (SVGRect(x=1, y=1, width=1, height=0), 0.0),
        # sub-paths with inverse winding direction
        (SVGPath(d="M0,0 L0,1 L1,1 L1,0 Z M2,0 L3,0 L3,1, L2,1 Z"), 2.0),
        # a straight line has no area
        (SVGPath(d="M1,1 L3,1"), 0.0),
        # open paths (no 'Z' at the end) are considered closed for area calculation
        (SVGPath(d="M1,1 L3,1 L2,0"), 1.0),
        # pathops.Path.area always return an absolute value >= 0
        (SVGPath(d="M0,1 L-1,0 L0,-1 L1,0 Z"), 2.0),
        (SVGPath(d="M0,1 L1,0 L0,-1 L-1,0 Z"), 2.0),
    ],
)
def test_path_area(shape, expected_result):
    assert svg_pathops.path_area(shape.as_cmd_seq(), shape.fill_rule) == expected_result

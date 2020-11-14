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

from picosvg.svg_types import SVGCircle, SVGPath, SVGRect
from picosvg.svg_transform import Affine2D
from picosvg.svg_reuse import normalize, affine_between
import pytest


@pytest.mark.parametrize(
    "s1, s2, expected_affine, tolerance",
    [
        # a rect and a circle can never be the same!
        (SVGRect(width=1, height=1), SVGCircle(r=1), None, 0.01),
        # same rect in the same place ftw
        (
            SVGRect(width=1, height=1),
            SVGRect(width=1, height=1),
            Affine2D.identity(),
            0.01,
        ),
        # same rect in the same place, different id
        (
            SVGRect(id="duck", width=1, height=1),
            SVGRect(id="duck", width=1, height=1),
            Affine2D.identity(),
            0.01,
        ),
        # same rect, offset
        (
            SVGRect(x=0, y=1, width=1, height=1),
            SVGRect(x=1, y=0, width=1, height=1),
            Affine2D.identity().translate(1, -1),
            0.01,
        ),
        # circles that may happen to match the ones Noto clock emoji
        (
            SVGCircle(cx=15.89, cy=64.13, r=4),
            SVGCircle(cx=64.89, cy=16.13, r=4),
            Affine2D.identity().translate(49, -48),
            0.01,
        ),
        # path observed in wild to normalize but not compute affine_between
        # caused by failure to normalize equivalent d attributes in affine_between
        (
            SVGPath(
                fill="#99AAB5", d="M18 12H2 c-1.104 0-2 .896-2 2h20c0-1.104-.896-2-2-2z"
            ),
            SVGPath(
                fill="#99AAB5", d="M34 12H18c-1.104 0-2 .896-2 2h20c0-1.104-.896-2-2-2z"
            ),
            Affine2D.identity().translate(16, 0),
            0.01,
        ),
        # Triangles facing one another, same size
        (
            SVGPath(d="m60,64 -50,-32 0,30 z"),
            SVGPath(d="m68,64 50,-32 0,30 z"),
            Affine2D(-1.0, 0.0, 0.0, 1.0, 128.0, -0.0),
            0.01,
        ),
        # Triangles, different rotation, different size
        (
            SVGPath(d="m50,100 -48,-75 81,0 z"),
            SVGPath(d="m70,64 50,-32 0,54 z"),
            Affine2D(a=-0.0, b=0.6667, c=-0.6667, d=-0.0, e=136.6667, f=30.6667),
            0.01,
        ),
        # TODO triangles, one point stretched not aligned with X or Y
        # A square and a rect; different scale for each axis
        (
            SVGRect(x=10, y=10, width=50, height=50),
            SVGRect(x=70, y=20, width=20, height=100),
            Affine2D(a=0.4, b=0.0, c=0.0, d=2.0, e=66.0, f=0.0),
            0.01,
        ),
        # Squares with same first edge but flipped on Y
        (
            SVGPath(d="M10,10 10,60 60,60 60,10 z"),
            SVGPath(d="M70,120 90,120 90,20 70,20 z"),
            Affine2D(a=0.0, b=-2.0, c=0.4, d=0.0, e=66.0, f=140.0),
            0.01,
        ),
        # Real example from Noto Emoji (when tolerance was 0.1), works at 0.2
        # https://github.com/googlefonts/picosvg/issues/138
        (
            SVGPath(
                d="M98.267,28.379 L115.157,21.769 Q116.007,21.437 116.843,21.802 Q117.678,22.168 118.011,23.017 Q118.343,23.867 117.978,24.703 Q117.612,25.538 116.763,25.871 L99.873,32.481 Q99.023,32.813 98.187,32.448 Q97.352,32.082 97.019,31.233 Q96.687,30.383 97.052,29.547 Q97.418,28.712 98.267,28.379 Z"
            ),
            SVGPath(
                d="M81.097,20.35 L79.627,4.2 Q79.544,3.291 80.128,2.59 Q80.712,1.889 81.62,1.807 Q82.529,1.724 83.23,2.308 Q83.931,2.892 84.013,3.8 L85.483,19.95 Q85.566,20.859 84.982,21.56 Q84.398,22.261 83.49,22.343 Q82.581,22.426 81.88,21.842 Q81.179,21.258 81.097,20.35 Z"
            ),
            Affine2D(a=0.249, b=-0.859, c=0.859, d=0.249, e=32.255, f=97.667),
            0.2,
        ),
    ],
)
def test_svg_reuse(s1, s2, expected_affine, tolerance):
    # if we can get an affine we should normalize to same shape
    if expected_affine:
        assert normalize(s1, tolerance) == normalize(s2, tolerance)
    else:
        assert normalize(s1, tolerance) != normalize(s2, tolerance)

    affine = affine_between(s1, s2, tolerance)
    if expected_affine:
        assert (
            affine
        ), f"No affine found between {s1.d} and {s2.d}. Expected {expected_affine}"
        # Round because we've seen issues with different test environments when overly fine
        affine = affine.round(4)
    assert (
        affine == expected_affine
    ), f"Unexpected affine found between {s1.d} and {s2.d}."

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
    "s1, s2, expected_affine",
    [
        # a rect and a circle can never be the same!
        (SVGRect(width=1, height=1), SVGCircle(r=1), None),
        # same rect in the same place ftw
        (SVGRect(width=1, height=1), SVGRect(width=1, height=1), Affine2D.identity()),
        # same rect in the same place, different id
        (
            SVGRect(id="duck", width=1, height=1),
            SVGRect(id="duck", width=1, height=1),
            Affine2D.identity(),
        ),
        # same rect, offset
        (
            SVGRect(x=0, y=1, width=1, height=1),
            SVGRect(x=1, y=0, width=1, height=1),
            Affine2D.identity().translate(1, -1),
        ),
        # circles that may happen to match the ones Noto clock emoji
        (
            SVGCircle(cx=15.89, cy=64.13, r=4),
            SVGCircle(cx=64.89, cy=16.13, r=4),
            Affine2D.identity().translate(49, -48),
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
        ),
        # Triangles facing one another, same size
        (
            SVGPath(
                d="m60,64 -50,-32 0,30 z"
            ),
            SVGPath(
                d="m68,64 50,-32 0,30 z"
            ),
            Affine2D(-1.0, 0.0, 0.0, 1.0, 128.0, -0.0),
        ),
        # Triangles, different rotation, different size
        (
            SVGPath(
                d="m50,100 -48,-75 81,0 z"
            ),
            SVGPath(
                d="m70,64 50,-32 0,54 z"
            ),
            Affine2D(a=-0.0, b=0.6667, c=-0.6667, d=-0.0, e=136.6667, f=30.6667),
        ),
        # Top heart, bottom heart from https://rsheeter.github.io/android_fonts/emoji.html?q=u:1f970
        # The heart is actually several parts, here just the main outline
        (
            SVGPath(
                d="M110.78,1.22c-7.06,2.83-7.68,10.86-7.68,10.86s-4.63-5.01-10.9-2.9c-7.53,2.54-11.32,10.62-5.22,19.34c6.98,9.97,29.38,12.81,29.38,12.81s12.53-16.37,10.79-29.35C125.74,1.43,116.12-0.92,110.78,1.22z"
            ),
            SVGPath(
                d="M116.31,96.26c-6.38-4.14-13.3-0.02-13.3-0.02s1.43-6.67-3.91-10.58c-6.41-4.7-15.2-3.13-18.81,6.88c-4.13,11.45,6.46,31.39,6.46,31.39s20.6,0.81,30.2-8.09C124.76,108.61,121.13,99.39,116.31,96.26z"
            ),
            Affine2D(-1.0, 0.0, 0.0, 1.0, 128.0, -0.0),
        ),
    ],
)
def test_svg_reuse(s1, s2, expected_affine):
    # if we can get an affine we should normalize to same shape
    if expected_affine:
        assert normalize(s1) == normalize(s2)
    else:
        assert normalize(s1) != normalize(s2)

    affine = affine_between(s1, s2)
    if expected_affine:
        assert affine
        # Round because we've seen issues with different test environments when overly fine
        affine = affine.round(4)
    assert affine == expected_affine

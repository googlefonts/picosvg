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

from picosvg.svg_types import SVGRect, SVGCircle
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
    ],
)
def test_svg_reuse(s1, s2, expected_affine):
    # if we can get an affine we should normalize to same shape
    if expected_affine:
        assert normalize(s1) == normalize(s2)
    else:
        assert normalize(s1) != normalize(s2)

    assert affine_between(s1, s2) == expected_affine

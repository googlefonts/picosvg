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
        # Tears from https://rsheeter.github.io/android_fonts/emoji.html?q=u:1f602
        (
            SVGPath(
                d="M100.69,57.09c0,0,17,0.47,23.79,13c2.84,5.26,3,14-2.88,17.19c-7.11,3.91-13.78-1.64-14.63-7.56C104.68,63.66,100.69,57.09,100.69,57.09z"
            ),
            SVGPath(
                d="M27.31,57.09c0,0-17,0.47-23.79,13C0.68,75.3,0.57,84,6.4,87.23c7.11,3.91,13.78-1.64,14.63-7.56C23.32,63.66,27.31,57.09,27.31,57.09z"
            ),
            Affine2D.identity(),
        ),
        # Top heart, bottom heart from https://rsheeter.github.io/android_fonts/emoji.html?q=u:1f970
        # This path is exported with 2 decimal places
        (
            SVGPath(
                d="M111.15,39.48c-2.24-0.61-22.59-6.5-25.8-18.44c-0.67-2.49-0.28-5.21,1.06-7.48c1.34-2.27,3.44-3.85,5.92-4.46c0.89-0.24,1.77-0.35,2.64-0.35c2.63,0,5.1,1.02,6.95,2.88l2.42,2.44l0.92-3.31c0.93-3.33,3.67-6.04,6.98-6.9c0.86-0.23,1.73-0.34,2.6-0.34c1.72,0,3.42,0.46,4.92,1.32c2.28,1.31,3.9,3.41,4.56,5.92C127.53,22.69,112.88,37.76,111.15,39.48z"
            ),
            SVGPath(
                d="M88.42,121.72c-1.15-2.01-11.26-20.36-5.15-30.95c1.71-2.96,4.93-4.8,8.42-4.8c1.71,0,3.37,0.46,4.81,1.33c3.07,1.78,4.95,5.02,4.93,8.47l-0.01,3.44l3-1.69c1.45-0.82,3.12-1.25,4.82-1.25c1.73,0,3.42,0.45,4.87,1.31c2.27,1.33,3.89,3.43,4.57,5.93c0.68,2.5,0.34,5.1-0.95,7.32c-6.1,10.59-26.76,10.89-29.1,10.89L88.42,121.72z"
            ),
            Affine2D(-1.0, 0.0, 0.0, 1.0, 128.0, -0.0),
        ),
        # Top heart, mid/left heart from https://rsheeter.github.io/android_fonts/emoji.html?q=u:1f970
        # This path is exported with 2 decimal places
        (
            SVGPath(
                d="M111.15,39.48c-2.24-0.61-22.59-6.5-25.8-18.44c-0.67-2.49-0.28-5.21,1.06-7.48c1.34-2.27,3.44-3.85,5.92-4.46c0.89-0.24,1.77-0.35,2.64-0.35c2.63,0,5.1,1.02,6.95,2.88l2.42,2.44l0.92-3.31c0.93-3.33,3.67-6.04,6.98-6.9c0.86-0.23,1.73-0.34,2.6-0.34c1.72,0,3.42,0.46,4.92,1.32c2.28,1.31,3.9,3.41,4.56,5.92C127.53,22.69,112.88,37.76,111.15,39.48z"
            ),
            SVGPath(
                d="M33.95,97.7c-2.33-0.16-23.23-1.86-28.7-12.83c-1.14-2.28-1.3-5-0.45-7.47c0.85-2.47,2.58-4.42,4.87-5.5c1.43-0.71,2.91-1.06,4.43-1.06c1.92,0,3.78,0.56,5.37,1.63l2.86,1.91l0.24-3.43c0.24-3.41,2.37-6.58,5.41-8.07c1.4-0.69,2.87-1.04,4.39-1.04c1.05,0,2.09,0.17,3.1,0.5c2.47,0.82,4.45,2.54,5.59,4.84C46.54,78.14,35.31,95.65,33.95,97.7z"
            ),
            Affine2D(-1.0, 0.0, 0.0, 1.0, 128.0, -0.0),
        ),
        # Top heart, bottom heart from https://rsheeter.github.io/android_fonts/emoji.html?q=u:1f970
        # This path is custom exported at high precision, at time of writing Noto svgs have 2 decimal places
        # This is an interesting example because one of the hearts has extra path segments
        # so a comparison of same # of very similar segments will fail.
        (
            SVGPath(
                d="M111.149414,39.480957c-2.240234-0.61377-22.592773-6.500488-25.797852-18.4375c-0.667969-2.485352-0.282227-5.212402,1.058594-7.481934c1.339844-2.268066,3.442383-3.852539,5.920898-4.461914c0.893555-0.237793,1.769531-0.353516,2.640625-0.353516c2.633789,0,5.101562,1.024414,6.949219,2.884277l2.423828,2.439453l0.921875-3.312988c0.926758-3.329102,3.665039-6.037109,6.976562-6.898438c0.859375-0.226562,1.731445-0.340332,2.59668-0.340332c1.716797,0,3.416992,0.455078,4.916016,1.316406c2.277344,1.305664,3.896484,3.40625,4.560547,5.915527C127.529297,22.690918,112.875,37.760254,111.149414,39.480957z"
            ),
            SVGPath(
                d="M88.421875,121.71875c-1.148438-2.014648-11.257812-20.357422-5.149414-30.950195c1.707031-2.960938,4.931641-4.800781,8.415039-4.800781c1.709961,0,3.373047,0.459961,4.811523,1.330078c3.067383,1.77832,4.945312,5.017578,4.933594,8.47168l-0.011719,3.439453l2.995117-1.691406c1.449219-0.818359,3.117188-1.250977,4.824219-1.250977c1.733398,0,3.417969,0.452148,4.873047,1.305664c2.271484,1.325195,3.892578,3.431641,4.569336,5.933594c0.679688,2.504883,0.342773,5.103516-0.946289,7.321289c-6.098633,10.587891-26.760742,10.893555-29.09668,10.893555L88.421875,121.71875z"
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
        assert affine, f"No affine found between {s1} and {s2}. Expected {expected_affine}"
        # Round because we've seen issues with different test environments when overly fine
        affine = affine.round(4)
    assert affine == expected_affine

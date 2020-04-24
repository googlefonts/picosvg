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

from picosvg.geometric_types import Point
from picosvg.arc_to_cubic import arc_to_cubic

import pytest


@pytest.mark.parametrize(
    "arc, expected_cubics",
    [
        # skip when start == end
        (((-1.0, 0.0), 1.0, 1.0, 0.0, False, False, (-1.0, 0.0)), []),
        # treat as straight line when either rx or ry == 0
        (
            ((-1.0, 0.0), 0.0, 1.0, 0.0, False, False, (0.0, 1.0)),
            [(None, None, (0.0, 1.0))],
        ),
        (
            ((-1.0, 0.0), 1.0, 0.0, 0.0, False, False, (0.0, 1.0)),
            [(None, None, (0.0, 1.0))],
        ),
        # large=False, sweep=False
        (
            ((-1.0, 0.0), 1.0, 1.0, 0.0, False, False, (0.0, 1.0)),
            [((-1.0, 0.552285), (-0.552285, 1.0), (0.0, 1.0))],
        ),
        # large=False, sweep=True
        (
            ((-1.0, 0.0), 1.0, 1.0, 0.0, False, True, (0.0, -1.0)),
            [((-1.0, -0.552285), (-0.552285, -1.0), (0.0, -1.0))],
        ),
        # large=True, sweep=False
        (
            ((-1.0, 0.0), 1.0, 1.0, 0.0, True, False, (0.0, 1.0)),
            [
                ((-1.552285, 0.0), (-2.0, 0.447715), (-2.0, 1.0)),
                ((-2.0, 1.552285), (-1.552285, 2.0), (-1.0, 2.0)),
                ((-0.447715, 2.0), (0.0, 1.552286), (0.0, 1.0)),
            ],
        ),
        # large=True, sweep=True
        (
            ((-1.0, 0.0), 1.0, 1.0, 0.0, True, True, (0.0, -1.0)),
            [
                ((-1.552285, 0.0), (-2.0, -0.447715), (-2.0, -1.0)),
                ((-2.0, -1.552285), (-1.552285, -2.0), (-1.0, -2.0)),
                ((-0.447715, -2.0), (0.0, -1.552285), (0.0, -1.0)),
            ],
        ),
        # out-of-range radii
        (
            ((-1.0, 0.0), 0.1, 0.1, 0.0, False, False, (0.0, 1.0)),
            [
                ((-1.2761423, 0.2761423), (-1.2761423, 0.7238576), (-1.0, 1.0)),
                ((-0.7238576, 1.2761423), (-0.2761423, 1.2761423), (0.0, 1.0)),
            ],
        ),
    ],
)
def test_arc_to_cubic(arc, expected_cubics):
    cubic_curves = list(arc_to_cubic(*arc))

    assert len(cubic_curves) == len(expected_cubics)
    for actual, expected in zip(cubic_curves, expected_cubics):
        assert (
            tuple(pytest.approx(p) if p is not None else p for p in actual) == expected
        )

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

# Functions meant to help discern if shapes are the same or not.

import dataclasses
from picosvg.svg_types import SVGShape, SVGPath
from typing import Optional, Tuple
from picosvg.svg_transform import Affine2D


def _first_move(shape: SVGShape) -> Tuple[float, float]:
    cmd, args = next(iter(shape.as_path()))
    if cmd.upper() != "M":
        raise ValueError(f"Path for {shape} should start with a move")
    return args


def normalize(shape: SVGShape) -> SVGShape:
    """Build a version of shape that will compare == to other shapes even if offset.

    Intended use is to normalize multiple shapes to identify opportunity for reuse."""
    shape = dataclasses.replace(shape, id="")
    x, y = _first_move(shape)
    shape = shape.as_path().move(-x, -y, inplace=True)
    return shape


def affine_between(s1: SVGShape, s2: SVGShape,) -> Optional[Affine2D]:
    """Returns the Affine2D to change s1 into s2 or None if no solution was found.

    Implementation starting *very* basic, can improve over time.
    """
    s1 = dataclasses.replace(s1, id="")
    s2 = dataclasses.replace(s2, id="")

    if s1 == s2:
        return Affine2D.identity()

    s1 = s1.as_path()
    s2 = s2.as_path()

    s1x, s1y = _first_move(s1)
    s2x, s2y = _first_move(s2)
    dx = s2x - s1x
    dy = s2y - s1y

    s1.move(dx, dy, inplace=True)

    if s1 == s2:
        return Affine2D.identity().translate(dx, dy)

    return None

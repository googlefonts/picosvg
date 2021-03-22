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

import math
from typing import NamedTuple, Optional, Union


DEFAULT_ALMOST_EQUAL_TOLERANCE = 1e-9
_PointOrVec = Union["Point", "Vector"]


def almost_equal(c1, c2, tolerance=DEFAULT_ALMOST_EQUAL_TOLERANCE) -> bool:
    return abs(c1 - c2) <= tolerance


class Point(NamedTuple):
    x: float = 0
    y: float = 0

    def _sub_pt(self, other: "Point") -> "Vector":
        return Vector(self.x - other.x, self.y - other.y)

    def _sub_vec(self, other: "Vector") -> "Point":
        return self.__class__(self.x - other.x, self.y - other.y)

    def __sub__(self, other: _PointOrVec) -> _PointOrVec:
        """Return a Point or Vector based on the type of other.

        If other is a Point, return Vector from other to self.
        If other is a Vector, return Point translated by -other Vector.
        """
        if isinstance(other, Point):
            return self._sub_pt(other)
        elif isinstance(other, Vector):
            return self._sub_vec(other)
        return NotImplemented

    def __add__(self, other: "Vector") -> "Point":
        """Return Point translated by other Vector"""
        if isinstance(other, Vector):
            return self.__class__(self.x + other.x, self.y + other.y)
        return NotImplemented

    def round(self, digits: int) -> "Point":
        return Point(round(self.x, digits), round(self.y, digits))

    def almost_equals(
        self, other: "Point", tolerance=DEFAULT_ALMOST_EQUAL_TOLERANCE
    ) -> bool:
        return almost_equal(self.x, other.x, tolerance) and almost_equal(
            self.y, other.y, tolerance
        )


class Vector(NamedTuple):
    x: float = 0
    y: float = 0

    def __add__(self, other: "Vector") -> "Vector":
        return self.__class__(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector") -> "Vector":
        return self.__class__(self.x - other.x, self.y - other.y)

    def __neg__(self) -> "Vector":
        return self * -1.0

    def __mul__(self, scalar: float) -> "Vector":
        """Multiply vector by a scalar value."""
        if not isinstance(scalar, (int, float)):
            return NotImplemented
        return self.__class__(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def perpendicular(self, clockwise: bool = False) -> "Vector":
        """Return Vector rotated 90 degrees counter-clockwise from self.

        If clockwise is True, return the other perpendicular vector.
        """
        # https://mathworld.wolfram.com/PerpendicularVector.html
        if clockwise:
            return self.__class__(self.y, -self.x)
        else:
            return self.__class__(-self.y, self.x)

    def norm(self) -> float:
        """Return the vector Euclidean norm (or length or magnitude)."""
        return math.sqrt(self.x * self.x + self.y * self.y)

    def unit(self) -> Optional["Vector"]:
        """Return the Unit Vector (of length 1), or None if self is a zero vector."""
        norm = self.norm()
        if norm != 0:
            return self.__class__(self.x / norm, self.y / norm)
        return None

    def dot(self, other: "Vector") -> float:
        """Return the Dot Product of self with other vector."""
        return self.x * other.x + self.y * other.y

    def projection(self, other: "Vector") -> "Vector":
        """Return the vector projection of self onto other vector."""
        norm = other.norm()
        if norm == 0:
            # it is more helpful for projection onto 0 to be 0 than an error
            return Vector()
        return self.dot(other) / norm * other.unit()


class Rect(NamedTuple):
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0

    def empty(self) -> bool:
        """Return True if the Rect's width or height is 0."""
        return self.w == 0 or self.h == 0

    def intersection(self, other: "Rect") -> Optional["Rect"]:
        def _overlap(start1, end1, start2, end2):
            start = max(start1, start2)
            end = min(end1, end2)
            if start >= end:
                return (0.0, 0.0)
            return (start, end)

        x1, x2 = _overlap(self.x, self.x + self.w, other.x, other.x + other.w)
        y1, y2 = _overlap(self.y, self.y + self.h, other.y, other.y + other.h)

        if x1 != x2 and y1 != y2:
            return Rect(x1, y1, x2 - x1, y2 - y1)
        return None

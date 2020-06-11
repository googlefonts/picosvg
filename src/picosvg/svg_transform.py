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

"""Helpers for https://www.w3.org/TR/SVG11/coords.html#TransformAttribute.

Focuses on converting to a sequence of affine matrices.
"""
import collections
from math import cos, sin, radians, tan
import re
from typing import NamedTuple, Tuple
from sys import float_info
from picosvg.geometric_types import Point, Rect, Vector


_SVG_ARG_FIXUPS = collections.defaultdict(
    lambda: lambda _: None,
    {
        "rotate": lambda args: _fix_rotate(args),
        "skewx": lambda args: _fix_rotate(args),
        "skewy": lambda args: _fix_rotate(args),
    },
)


# 2D affine transform.
#
# View as vector of 6 values or matrix:
#
# a   c   e
# b   d   f
class Affine2D(NamedTuple):
    a: float
    b: float
    c: float
    d: float
    e: float
    f: float

    @staticmethod
    def identity():
        return Affine2D._identity

    @staticmethod
    def fromstring(raw_transform):
        return parse_svg_transform(raw_transform)

    @staticmethod
    def product(first: "Affine2D", second: "Affine2D") -> "Affine2D":
        """Returns the product of first x second.

        Order matters; meant to make that a bit more explicit.
        """
        return Affine2D(
            first.a * second.a + first.b * second.c,
            first.a * second.b + first.b * second.d,
            first.c * second.a + first.d * second.c,
            first.c * second.b + first.d * second.d,
            second.a * first.e + second.c * first.f + second.e,
            second.b * first.e + second.d * first.f + second.f,
        )

    def matrix(self, a, b, c, d, e, f):
        return Affine2D.product(Affine2D(a, b, c, d, e, f), self)

    # https://www.w3.org/TR/SVG11/coords.html#TranslationDefined
    def translate(self, tx, ty=0):
        if (0, 0) == (tx, ty):
            return self
        return self.matrix(1, 0, 0, 1, tx, ty)

    def gettranslate(self) -> Tuple[float, float]:
        return (self.e, self.f)

    def getscale(self) -> Tuple[float, float]:
        return (self.a, self.d)

    # https://www.w3.org/TR/SVG11/coords.html#ScalingDefined
    def scale(self, sx, sy=None):
        if sy is None:
            sy = sx
        return self.matrix(sx, 0, 0, sy, 0, 0)

    # https://www.w3.org/TR/SVG11/coords.html#RotationDefined
    # Note that rotation here is in radians
    def rotate(self, a, cx=0.0, cy=0.0):
        return (
            self.translate(cx, cy)
            .matrix(cos(a), sin(a), -sin(a), cos(a), 0, 0)
            .translate(-cx, -cy)
        )

    # https://www.w3.org/TR/SVG11/coords.html#SkewXDefined
    def skewx(self, a):
        return self.matrix(1, 0, tan(a), 1, 0, 0)

    # https://www.w3.org/TR/SVG11/coords.html#SkewYDefined
    def skewy(self, a):
        return self.matrix(1, tan(a), 0, 1, 0, 0)

    def determinant(self) -> float:
        return self.a * self.d - self.b * self.c

    def is_degenerate(self) -> bool:
        """Return True if [a b c d] matrix is degenerate (determinant is 0)."""
        return abs(self.determinant()) <= float_info.epsilon

    def inverse(self):
        """Return the inverse Affine2D transformation.

        Raises ValueError if it's degenerate and thus non-invertible."""
        if self == self.identity():
            return self
        elif self.is_degenerate():
            raise ValueError(f"Degenerate matrix is non-invertible: {self!r}")
        a, b, c, d, e, f = self
        det = self.determinant()
        a, b, c, d = d / det, -b / det, -c / det, a / det
        e = -a * e - c * f
        f = -b * e - d * f
        return self.__class__(a, b, c, d, e, f)

    def map_point(self, pt: Tuple[float, float]) -> Point:
        """Return Point (x, y) multiplied by Affine2D."""
        x, y = pt
        return Point(self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f)

    def map_vector(self, vec: Tuple[float, float]) -> Vector:
        """Return Vector (x, y) multiplied by Affine2D, treating translation as zero."""
        x, y = vec
        return Vector(self.a * x + self.c * y, self.b * x + self.d * y)

    @classmethod
    def rect_to_rect(cls, src: Rect, dst: Rect) -> "Affine2D":
        """ Return Affine2D set to scale and translate src Rect to dst Rect.
        The mapping completely fills dst, it does not preserve aspect ratio.
        """
        if src.empty():
            return cls.identity()
        if dst.empty():
            return cls(0, 0, 0, 0, 0, 0)
        sx = dst.w / src.w
        sy = dst.h / src.h
        tx = dst.x - src.x * sx
        ty = dst.y - src.y * sy
        return cls(sx, 0, 0, sy, tx, ty)


Affine2D._identity = Affine2D(1, 0, 0, 1, 0, 0)


def _fix_rotate(args):
    args[0] = radians(args[0])


def parse_svg_transform(raw_transform: str):
    # much simpler to read if we do stages rather than a single regex
    transform = Affine2D.identity()

    svg_transforms = re.split(r"(?<=[)])\s*[,\s]\s*(?=\w)", raw_transform)
    for svg_transform in svg_transforms:
        match = re.match(
            r"(?i)(matrix|translate|scale|rotate|skewX|skewY)\((.*)\)", svg_transform
        )
        if not match:
            raise ValueError(f"Unable to parse {raw_transform}")

        op = match.group(1).lower()
        args = [float(p) for p in re.split(r"\s*[,\s]\s*", match.group(2))]
        _SVG_ARG_FIXUPS[op](args)
        transform = getattr(transform, op)(*args)

    return transform

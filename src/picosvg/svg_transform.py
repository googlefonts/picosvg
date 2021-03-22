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
from functools import reduce
from math import cos, sin, radians, tan, hypot
import re
from typing import NamedTuple, Sequence, Tuple
from sys import float_info
from picosvg.geometric_types import (
    Point,
    Rect,
    Vector,
    DEFAULT_ALMOST_EQUAL_TOLERANCE,
    almost_equal,
)
from picosvg.svg_meta import ntos


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
    def flip_y():
        return Affine2D._flip_y

    @staticmethod
    def identity():
        return Affine2D._identity

    @staticmethod
    def degenerate():
        return Affine2D._degnerate

    @staticmethod
    def fromstring(raw_transform):
        return parse_svg_transform(raw_transform)

    def tostring(self):
        if self == Affine2D.identity().translate(*self.gettranslate()):
            return f'translate({", ".join(ntos(v) for v in self.gettranslate())})'
        return f'matrix({" ".join(ntos(v) for v in self)})'

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

        The inverse of a degenerate Affine2D is itself degenerate."""
        if self == self.identity():
            return self
        elif self.is_degenerate():
            return Affine2D.degenerate()
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
    def compose_ltr(cls, affines: Sequence["Affine2D"]) -> "Affine2D":
        """Creates merged transform equivalent to applying transforms left-to-right order.

        Affines apply like functions - f(g(x)) - so we merge them in reverse order.
        """
        return reduce(
            lambda acc, a: cls.product(a, acc), reversed(affines), cls.identity()
        )

    def round(self, digits: int) -> "Affine2D":
        return Affine2D(*(round(v, digits) for v in self))

    @classmethod
    def rect_to_rect(cls, src: Rect, dst: Rect) -> "Affine2D":
        """Return Affine2D set to scale and translate src Rect to dst Rect.
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

    def almost_equals(
        self, other: "Affine2D", tolerance=DEFAULT_ALMOST_EQUAL_TOLERANCE
    ):
        return all(almost_equal(v1, v2, tolerance) for v1, v2 in zip(self, other))

    def decompose_scale(self) -> Tuple["Affine2D", "Affine2D"]:
        """Split affine into a scale component and whatever remains.

        Return the affine components in LTR order, such that mapping a point
        consecutively by each gives the same result as mapping the same by the
        original combined affine.

        For reference, see SkMatrix::decomposeScale
        https://github.com/google/skia/blob/e0707b7/src/core/SkMatrix.cpp#L1577-L1597
        """
        sx = hypot(self.a, self.b)
        sy = hypot(self.c, self.d)
        scale = Affine2D(sx, 0, 0, sy, 0, 0)
        remaining = Affine2D.compose_ltr((scale.inverse(), self))
        return scale, remaining

    def decompose_translation(self) -> Tuple["Affine2D", "Affine2D"]:
        """Split affine into a translation and a 2x2 component.

        Return the affine components in LTR order, such that mapping a point
        consecutively by each gives the same result as mapping the same by the
        original combined affine.
        """
        affine_prime = self._replace(e=0, f=0)
        #  no translate? nop!
        if self.almost_equals(affine_prime):
            return Affine2D.identity(), affine_prime

        a, b, c, d, e, f = self
        # We need x`, y` such that matrix a b c d 0 0 yields same
        # result as x, y with a b c d e f
        # That is:
        # 1)  ax` + cy` + 0 = ax + cy + e
        # 2)  bx` + dy` + 0 = bx + dy + f
        #                   ^ rhs is a known scalar; we'll call r1, r2
        # multiply 1) by b/a so when subtracted from 2) we eliminate x`
        # 1)  bx` + (b/a)cy` = (b/a) * r1
        # 2) - 1)  bx` - bx` + dy` - (b/a)cy` = r2 - (b/a) * r1
        #         y` = (r2 - (b/a) * r1) / (d - (b/a)c)

        # for the special case of origin (0,0) the math below could be simplified
        # futher but I keep the expanded version for clarity sake
        x, y = (0, 0)
        r1, r2 = self.map_point((x, y))
        if not almost_equal(a, 0):
            y_prime = (r2 - r1 * b / a) / (d - b * c / a)

            # Sub y` into 1)
            # 1) x` = (r1 - cy`) / a
            x_prime = (r1 - c * y_prime) / a
        else:
            # if a == 0 then above gives div / 0. Take a simpler path.
            # 1) 0x` + cy` + 0 = 0x + cy + e
            #    y` = y + e/c
            y_prime = y + e / c
            # Sub y` into 2)
            # 2)  bx` + dy` + 0 = bx + dy + f
            #      x` = x + dy/b + f/b - dy`/b
            x_prime = x + (d * y / b) + (f / b) - (d * y_prime / b)

        # basically this says "by how much do I need to pre-translate things so
        # that when I subsequently apply the 2x2 portion of the original affine
        # (with the translation zeroed) it'll land me in the same place?"
        translation = Affine2D.identity().translate(x_prime, y_prime)
        # sanity check that combining the two affines gives back self
        assert self.almost_equals(Affine2D.compose_ltr((translation, affine_prime)))
        return translation, affine_prime


Affine2D._identity = Affine2D(1, 0, 0, 1, 0, 0)
Affine2D._degnerate = Affine2D(0, 0, 0, 0, 0, 0)
Affine2D._flip_y = Affine2D(1, 0, 0, -1, 0, 0)


def _fix_rotate(args):
    args[0] = radians(args[0])


def parse_svg_transform(raw_transform: str):
    # much simpler to read if we do stages rather than a single regex
    # one day it might be worth writing a real parser
    transform = Affine2D.identity()

    for match in re.finditer(
        r"(?i)(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)", raw_transform
    ):
        op = match.group(1).lower()
        args = [float(p) for p in re.split(r"\s*[,\s]\s*", match.group(2).strip())]
        _SVG_ARG_FIXUPS[op](args)
        transform = getattr(transform, op)(*args)

    return transform

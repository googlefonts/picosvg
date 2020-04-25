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

"""Convert SVG Path's elliptical arcs to Bezier curves.

The code is adapted from FontTools fontTools/svgLib/path/arc.py, which in turn
is adapted from Blink's SVGPathNormalizer::DecomposeArcToCubic:
https://github.com/chromium/chromium/blob/93831f2/third_party/blink/renderer/core/svg/svg_path_parser.cc#L169-L278
"""
from math import atan2, ceil, cos, fabs, isfinite, pi, radians, sin, sqrt, tan
from typing import Iterator, NamedTuple, Optional, Tuple
from picosvg.geometric_types import Point, Vector
from picosvg.svg_transform import Affine2D


TWO_PI = 2 * pi
PI_OVER_TWO = 0.5 * pi


class CenterParametrization(NamedTuple):
    theta1: float
    theta_arc: float
    center_point: Point


class EllipticalArc(NamedTuple):
    start_point: Point
    rx: float
    ry: float
    rotation: float
    large: int
    sweep: int
    end_point: Point

    def is_straight_line(self) -> bool:
        # If rx = 0 or ry = 0 then this arc is treated as a straight line segment (a
        # "lineto") joining the endpoints.
        # http://www.w3.org/TR/SVG/implnote.html#ArcOutOfRangeParameters
        rx = fabs(self.rx)
        ry = fabs(self.ry)
        if not (rx and ry):
            return True
        return False

    def is_zero_length(self):
        return self.end_point == self.start_point

    def correct_out_of_range_radii(self) -> "EllipticalArc":
        # Check if the radii are big enough to draw the arc, scale radii if not.
        # http://www.w3.org/TR/SVG/implnote.html#ArcCorrectionOutOfRangeRadii
        if self.is_straight_line() or self.is_zero_length():
            return self

        mid_point_distance = (self.start_point - self.end_point) * 0.5

        # SVG rotation is expressed in degrees, whereas Affin2D.rotate uses radians
        angle = radians(self.rotation)
        point_transform = Affine2D.identity().rotate(-angle)

        transformed_mid_point = point_transform.map_vector(mid_point_distance)
        rx = self.rx
        ry = self.ry
        square_rx = rx * rx
        square_ry = ry * ry
        square_x = transformed_mid_point.x * transformed_mid_point.x
        square_y = transformed_mid_point.y * transformed_mid_point.y

        radii_scale = square_x / square_rx + square_y / square_ry
        if radii_scale > 1:
            rx *= sqrt(radii_scale)
            ry *= sqrt(radii_scale)
            return self._replace(rx=rx, ry=ry)

        return self

    # https://www.w3.org/TR/SVG/implnote.html#ArcConversionEndpointToCenter
    def end_to_center_parametrization(self) -> CenterParametrization:
        if self.is_straight_line() or self.is_zero_length():
            raise ValueError(f"Can't compute center parametrization for {self}")

        angle = radians(self.rotation)
        point_transform = (
            Affine2D.identity().scale(1 / self.rx, 1 / self.ry).rotate(-angle)
        )

        point1 = point_transform.map_point(self.start_point)
        point2 = point_transform.map_point(self.end_point)
        delta = point2 - point1

        d = delta.x * delta.x + delta.y * delta.y
        scale_factor_squared = max(1 / d - 0.25, 0.0)

        scale_factor = sqrt(scale_factor_squared)
        if self.sweep == self.large:
            scale_factor = -scale_factor

        delta *= scale_factor
        center_point = point1 + (point2 - point1) * 0.5 + Vector(-delta.y, delta.x)
        v1 = point1 - center_point
        v2 = point2 - center_point

        theta1 = atan2(v1.y, v1.x)
        theta2 = atan2(v2.y, v2.x)

        theta_arc = theta2 - theta1
        if theta_arc < 0 and self.sweep:
            theta_arc += TWO_PI
        elif theta_arc > 0 and not self.sweep:
            theta_arc -= TWO_PI

        center_point = point_transform.inverse().map_point(center_point)

        return CenterParametrization(theta1, theta_arc, center_point)


def _arc_to_cubic(arc: EllipticalArc) -> Iterator[Tuple[Point, Point, Point]]:
    arc = arc.correct_out_of_range_radii()
    arc_params = arc.end_to_center_parametrization()

    point_transform = (
        Affine2D.identity()
        .translate(arc_params.center_point.x, arc_params.center_point.y)
        .rotate(radians(arc.rotation))
        .scale(arc.rx, arc.ry)
    )

    # Some results of atan2 on some platform implementations are not exact
    # enough. So that we get more cubic curves than expected here. Adding 0.001f
    # reduces the count of sgements to the correct count.
    num_segments = int(ceil(fabs(arc_params.theta_arc / (PI_OVER_TWO + 0.001))))
    for i in range(num_segments):
        start_theta = arc_params.theta1 + i * arc_params.theta_arc / num_segments
        end_theta = arc_params.theta1 + (i + 1) * arc_params.theta_arc / num_segments

        t = (4 / 3) * tan(0.25 * (end_theta - start_theta))
        if not isfinite(t):
            return

        sin_start_theta = sin(start_theta)
        cos_start_theta = cos(start_theta)
        sin_end_theta = sin(end_theta)
        cos_end_theta = cos(end_theta)

        point1 = Point(
            cos_start_theta - t * sin_start_theta, sin_start_theta + t * cos_start_theta
        )
        end_point = Point(cos_end_theta, sin_end_theta)
        point2 = end_point + Vector(t * sin_end_theta, -t * cos_end_theta)

        point1 = point_transform.map_point(point1)
        point2 = point_transform.map_point(point2)
        end_point = point_transform.map_point(end_point)

        yield point1, point2, end_point


def arc_to_cubic(
    start_point: Tuple[float, float],
    rx: float,
    ry: float,
    rotation: float,
    large: int,
    sweep: int,
    end_point: Tuple[float, float],
) -> Iterator[Tuple[Optional[Point], Optional[Point], Point]]:
    """Convert arc to cubic(s).

    start/end point are (x,y) tuples with absolute coordinates.
    See https://skia.org/user/api/SkPath_Reference#SkPath_arcTo_4
    Note in particular:
        SVG sweep-flag value is opposite the integer value of sweep;
        SVG sweep-flag uses 1 for clockwise, while kCW_Direction cast to int is zero.

    Yields 3-tuples of Points for each Cubic bezier, i.e. two off-curve points and
    one on-curve end point.

    If either rx or ry is 0, the arc is treated as a straight line joining the end
    points, and a (None, None, arc.end_point) tuple is yielded.

    Yields empty iterator if arc has zero length.
    """
    if not isinstance(start_point, Point):
        start_point = Point(*start_point)
    if not isinstance(end_point, Point):
        end_point = Point(*end_point)

    arc = EllipticalArc(start_point, rx, ry, rotation, large, sweep, end_point)
    if arc.is_zero_length():
        return
    elif arc.is_straight_line():
        yield None, None, arc.end_point
    else:
        yield from _arc_to_cubic(arc)

"""Convert SVG Path's elliptical arcs to Bezier curves.

Adapted from FontTools fontTools/svgLib/path/arc.py,
Lib/fontTools/misc/transform.py. If this toy works out will
figure out how to merge things together more cleanly.

The code is mostly adapted from Blink's SVGPathNormalizer::DecomposeArcToCubic
https://github.com/chromium/chromium/blob/93831f2/third_party/
blink/renderer/core/svg/svg_path_parser.cc#L169-L278
"""
import collections
from math import atan2, ceil, cos, fabs, isfinite, pi, radians, sin, sqrt, tan


TWO_PI = 2 * pi
PI_OVER_TWO = 0.5 * pi

_EPSILON = 1e-15
_ONE_EPSILON = 1 - _EPSILON
_MINUS_ONE_EPSILON = -1 + _EPSILON


def _normSinCos(v):
    if abs(v) < _EPSILON:
        v = 0
    elif v > _ONE_EPSILON:
        v = 1
    elif v < _MINUS_ONE_EPSILON:
        v = -1
    return v

ArcTuple = collections.namedtuple('ArcTuple',
                                  ['start_point', 'rx', 'ry', 'rotation',
                                  'large', 'sweep', 'end_point', 'angle'])

ArcParameterizationTuple = collections.namedtuple('ArcParameterizationTuple',
                                                  ['theta1', 'theta2', 
                                                   'theta_arc', 'center_point'])

_AFFINE_IDENTITY = (1, 0, 0, 1, 0, 0)

def _transform_transform(t1, t2):
    return (t1[0]*t2[0] + t1[1]*t2[2],
            t1[0]*t2[1] + t1[1]*t2[3],
            t1[2]*t2[0] + t1[3]*t2[2],
            t1[2]*t2[1] + t1[3]*t2[3],
            t2[0]*t1[4] + t2[2]*t1[5] + t2[4],
            t2[1]*t1[4] + t2[3]*t1[5] + t2[5])

def _rotate(transform, angle):
    c = _normSinCos(cos(angle))
    s = _normSinCos(sin(angle))
    return _transform_transform(transform, (c, s, -s, c, 0, 0))

def _scale(transform, scale_x, scale_y):
    return _transform_transform(transform, (scale_x, 0, 0, scale_y, 0, 0))

def _transform_pt(transform, pt):
    x = pt.real
    y = pt.imag
    return complex(transform[0]*x + transform[2]*y + transform[4],
                   transform[1]*x + transform[3]*y + transform[5])

# https://www.w3.org/TR/SVG/implnote.html#ArcConversionEndpointToCenter
def _end_to_center_parameterization(arc):
    # these derived attributes are computed by the _parametrize method
    center_point = theta1 = theta2 = theta_arc = None

    # If rx = 0 or ry = 0 then this arc is treated as a straight line segment (a
    # "lineto") joining the endpoints.
    # http://www.w3.org/TR/SVG/implnote.html#ArcOutOfRangeParameters
    rx = fabs(arc.rx)
    ry = fabs(arc.ry)
    if not (rx and ry):
        return False

    # If the start point and end point for the arc are identical, it should
    # be treated as a zero length path. This ensures continuity in animations.
    if arc.end_point == arc.start_point:
        return False

    mid_point_distance = (arc.start_point - arc.end_point) * 0.5

    point_transform = _rotate(_AFFINE_IDENTITY, -arc.angle)

    transformed_mid_point = _transform_pt(point_transform, mid_point_distance)
    square_rx = rx * rx
    square_ry = ry * ry
    square_x = transformed_mid_point.real * transformed_mid_point.real
    square_y = transformed_mid_point.imag * transformed_mid_point.imag

    # Check if the radii are big enough to draw the arc, scale radii if not.
    # http://www.w3.org/TR/SVG/implnote.html#ArcCorrectionOutOfRangeRadii
    radii_scale = square_x / square_rx + square_y / square_ry
    if radii_scale > 1:
        rx *= sqrt(radii_scale)
        ry *= sqrt(radii_scale)
        arc = arc._replace(rx = rx, ry = ry)

    point_transform = _scale(_AFFINE_IDENTITY, 1 / rx, 1 / ry)
    point_transform = _rotate(point_transform, -arc.angle)

    point1 = _transform_pt(point_transform, arc.start_point)
    point2 = _transform_pt(point_transform, arc.end_point)
    delta = point2 - point1

    d = delta.real * delta.real + delta.imag * delta.imag
    scale_factor_squared = max(1 / d - 0.25, 0.0)

    scale_factor = sqrt(scale_factor_squared)
    if arc.sweep == arc.large:
        scale_factor = -scale_factor

    delta *= scale_factor
    center_point = (point1 + point2) * 0.5
    center_point += complex(-delta.imag, delta.real)
    point1 -= center_point
    point2 -= center_point

    theta1 = atan2(point1.imag, point1.real)
    theta2 = atan2(point2.imag, point2.real)

    theta_arc = theta2 - theta1
    if theta_arc < 0 and arc.sweep:
        theta_arc += TWO_PI
    elif theta_arc > 0 and not arc.sweep:
        theta_arc -= TWO_PI

    return ArcParameterizationTuple(theta1, theta1 + theta_arc, theta_arc, center_point)

def _arc_to_cubic(arc):
    arc_params = _end_to_center_parameterization(arc)
    if not arc_params:
        return

    point_transform = _rotate(_AFFINE_IDENTITY, arc.angle)
    point_transform = _scale(point_transform, arc.rx, arc.ry)

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

        point1 = complex(
            cos_start_theta - t * sin_start_theta,
            sin_start_theta + t * cos_start_theta,
        )
        point1 += arc_params.center_point
        target_point = complex(cos_end_theta, sin_end_theta)
        target_point += arc_params.center_point
        point2 = target_point
        point2 += complex(t * sin_end_theta, -t * cos_end_theta)

        point1 = _transform_pt(point_transform, point1)
        point2 = _transform_pt(point_transform, point2)
        target_point = _transform_pt(point_transform, target_point)

        yield point1, point2, target_point

def arc_to_cubic(start_point, rx, ry, rotation, large, sweep, end_point):
    """Convert arc to cubic(s).

    start/end point are absolute, either complex or sequence of x,y.

    See https://skia.org/user/api/SkPath_Reference#SkPath_arcTo_4
    Note in particular:
        SVG sweep-flag value is opposite the integer value of sweep;
        SVG sweep-flag uses 1 for clockwise, while kCW_Direction cast to int is zero.
    Yields 3-tuples of complex values, each representing a point
    """
    if not isinstance(start_point, complex):
        start_point = complex(*start_point)
    if not isinstance(end_point, complex):
        end_point = complex(*end_point)
    # SVG arc's rotation angle is expressed in degrees, whereas Transform.rotate
    # uses radians
    angle = radians(rotation)
    arc = ArcTuple(start_point, rx, ry, rotation, large, sweep, end_point, angle)
    for t in _arc_to_cubic(arc):
        yield t








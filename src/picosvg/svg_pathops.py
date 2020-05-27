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

"""SVGPath <=> skia-pathops constructs to enable ops on paths."""
import functools
import pathops
from typing import Sequence, Tuple
from picosvg.svg_meta import SVGCommand, SVGCommandGen, SVGCommandSeq
from picosvg.svg_transform import Affine2D


# Absolutes coords assumed
# A should never occur because we convert arcs to cubics
# S,T should never occur because we eliminate shorthand
_SVG_CMD_TO_SKIA_FN = {
    "M": pathops.Path.moveTo,
    "L": pathops.Path.lineTo,
    "Q": pathops.Path.quadTo,
    "Z": pathops.Path.close,
    "C": pathops.Path.cubicTo,
}

_SVG_TO_SKIA_LINE_CAP = {
    "butt": pathops.LineCap.BUTT_CAP,
    "round": pathops.LineCap.ROUND_CAP,
    "square": pathops.LineCap.SQUARE_CAP,
}

_SVG_TO_SKIA_LINE_JOIN = {
    "miter": pathops.LineJoin.MITER_JOIN,
    "round": pathops.LineJoin.ROUND_JOIN,
    "bevel": pathops.LineJoin.BEVEL_JOIN,
    # No arcs or miter-clip
}


def _simple_skia_to_svg(svg_cmd, points) -> SVGCommandGen:
    # pathops.Path gives us sequences of points, flatten 'em
    yield (svg_cmd, tuple(c for pt in points for c in pt))


def _qcurveto_to_svg(points) -> SVGCommandGen:
    for (control_pt, end_pt) in pathops.decompose_quadratic_segment(points):
        yield ("Q", control_pt + end_pt)


def _end_path(points) -> SVGCommandGen:
    if points:
        raise ValueError("endPath should have no points")
    return  # pytype: disable=bad-return-type
    yield


_SKIA_CMD_TO_SVG_CMD = {
    # simple conversions
    "moveTo": functools.partial(_simple_skia_to_svg, "M"),
    "lineTo": functools.partial(_simple_skia_to_svg, "L"),
    "quadTo": functools.partial(_simple_skia_to_svg, "Q"),
    "curveTo": functools.partial(_simple_skia_to_svg, "C"),
    "closePath": functools.partial(_simple_skia_to_svg, "Z"),
    # more interesting conversions
    "qCurveTo": _qcurveto_to_svg,
    # nop
    "endPath": _end_path,
}


def skia_path(svg_cmds: SVGCommandSeq):
    sk_path = pathops.Path()
    for cmd, args in svg_cmds:
        if cmd not in _SVG_CMD_TO_SKIA_FN:
            raise ValueError(f'No mapping to Skia for "{cmd} {args}"')
        _SVG_CMD_TO_SKIA_FN[cmd](sk_path, *args)
    return sk_path


def svg_commands(skia_path: pathops.Path) -> SVGCommandGen:
    for cmd, points in skia_path.segments:
        if cmd not in _SKIA_CMD_TO_SVG_CMD:
            raise ValueError(f'No mapping to svg for "{cmd} {points}"')
        for svg_cmd, svg_args in _SKIA_CMD_TO_SVG_CMD[cmd](points):
            yield (svg_cmd, svg_args)


def _do_pathop(op: str, svg_cmd_seqs: Sequence[SVGCommandSeq]) -> SVGCommandGen:
    if not svg_cmd_seqs:
        return  # pytype: disable=bad-return-type
    sk_path = skia_path(svg_cmd_seqs[0])
    for svg_cmds in svg_cmd_seqs[1:]:
        sk_path2 = skia_path(svg_cmds)
        sk_path = pathops.op(sk_path, sk_path2, op)
    return svg_commands(sk_path)


def union(*svg_cmd_seqs: SVGCommandSeq) -> SVGCommandGen:
    return _do_pathop(pathops.PathOp.UNION, svg_cmd_seqs)


def intersection(*svg_cmd_seqs) -> SVGCommandGen:
    return _do_pathop(pathops.PathOp.INTERSECTION, svg_cmd_seqs)


def transform(svg_cmds: SVGCommandSeq, affine: Affine2D) -> SVGCommandGen:
    sk_path = skia_path(svg_cmds).transform(*affine)
    return svg_commands(sk_path)


def stroke(
    svg_cmds: SVGCommandSeq,
    svg_linecap: str,
    svg_linejoin: str,
    stroke_width: float,
    stroke_miterlimit: float,
    tolerance: float,
) -> SVGCommandGen:
    """Create a path that is shape with it's stroke applied."""
    cap = _SVG_TO_SKIA_LINE_CAP.get(svg_linecap, None)
    if cap is None:
        raise ValueError(f"Unsupported cap {svg_linecap}")
    join = _SVG_TO_SKIA_LINE_JOIN.get(svg_linejoin, None)
    if join is None:
        raise ValueError(f"Unsupported join {svg_linejoin}")
    sk_path = skia_path(svg_cmds)
    sk_path.stroke(stroke_width, cap, join, stroke_miterlimit)

    # nuke any conics that snuck in (e.g. with stroke-linecap="round")
    sk_path.convertConicsToQuads(tolerance)

    return svg_commands(sk_path)


def bounding_box(svg_cmds: SVGCommandSeq):
    return skia_path(svg_cmds).bounds

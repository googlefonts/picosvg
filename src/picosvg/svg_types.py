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

import copy
import dataclasses
from picosvg.geometric_types import Point, Rect
from picosvg import svg_meta
from picosvg import svg_pathops
from picosvg.arc_to_cubic import arc_to_cubic
from picosvg.svg_path_iter import parse_svg_path
from picosvg.svg_transform import Affine2D
from typing import Generator, Iterable


def _explicit_lines_callback(subpath_start, curr_pos, cmd, args, *_):
    del subpath_start
    if cmd == "v":
        args = (0, args[0])
    elif cmd == "V":
        args = (curr_pos.x, args[0])
    elif cmd == "h":
        args = (args[0], 0)
    elif cmd == "H":
        args = (args[0], curr_pos.y)
    else:
        return ((cmd, args),)  # nothing changes

    if cmd.islower():
        cmd = "l"
    else:
        cmd = "L"

    return ((cmd, args),)


def _relative_to_absolute(curr_pos, cmd, args):
    x_coord_idxs, y_coord_idxs = svg_meta.cmd_coords(cmd)
    if cmd.islower():
        cmd = cmd.upper()
        args = list(args)  # we'd like to mutate 'em
        for x_coord_idx in x_coord_idxs:
            args[x_coord_idx] += curr_pos.x
        for y_coord_idx in y_coord_idxs:
            args[y_coord_idx] += curr_pos.y

    return (cmd, tuple(args))


def _next_pos(curr_pos, cmd, cmd_args):
    # update current position
    x_coord_idxs, y_coord_idxs = svg_meta.cmd_coords(cmd)
    new_x, new_y = curr_pos
    if cmd.isupper():
        if x_coord_idxs:
            new_x = 0
        if y_coord_idxs:
            new_y = 0

    if x_coord_idxs:
        new_x += cmd_args[x_coord_idxs[-1]]
    if y_coord_idxs:
        new_y += cmd_args[y_coord_idxs[-1]]

    return Point(new_x, new_y)


def _move_endpoint(curr_pos, cmd, cmd_args, new_endpoint):
    # we need to be able to alter both axes
    ((cmd, cmd_args),) = _explicit_lines_callback(None, curr_pos, cmd, cmd_args)

    x_coord_idxs, y_coord_idxs = svg_meta.cmd_coords(cmd)
    cmd_args = list(cmd_args)  # we'd like to mutate
    new_x, new_y = new_endpoint
    if cmd.islower():
        new_x = new_x - curr_pos.x
        new_y = new_y - curr_pos.y

    cmd_args[x_coord_idxs[-1]] = new_x
    cmd_args[y_coord_idxs[-1]] = new_y

    return cmd, cmd_args


# Subset of https://www.w3.org/TR/SVG11/painting.html
@dataclasses.dataclass
class SVGShape:
    id: str = ""
    clip_path: str = ""
    clip_rule: str = "nonzero"
    fill: str = "black"
    fill_rule: str = "nonzero"
    stroke: str = "none"
    stroke_width: float = 1.0
    stroke_linecap: str = "butt"
    stroke_linejoin: str = "miter"
    stroke_miterlimit: float = 4
    stroke_dasharray: str = ""
    stroke_dashoffset: float = 1.0
    stroke_opacity: float = 1.0
    opacity: float = 1.0
    transform: str = ""
    style: str = ""

    def _copy_common_fields(
        self,
        id,
        clip_path,
        clip_rule,
        fill,
        fill_rule,
        stroke,
        stroke_width,
        stroke_linecap,
        stroke_linejoin,
        stroke_miterlimit,
        stroke_dasharray,
        stroke_dashoffset,
        stroke_opacity,
        opacity,
        transform,
        style,
    ):
        self.id = id
        self.clip_path = clip_path
        self.clip_rule = clip_rule
        self.fill = fill
        self.fill_rule = fill_rule
        self.stroke = stroke
        self.stroke_width = stroke_width
        self.stroke_linecap = stroke_linecap
        self.stroke_linejoin = stroke_linejoin
        self.stroke_miterlimit = stroke_miterlimit
        self.stroke_dasharray = stroke_dasharray
        self.stroke_dashoffset = stroke_dashoffset
        self.stroke_opacity = stroke_opacity
        self.opacity = opacity
        self.transform = transform
        self.style = style

    def might_paint(self) -> bool:
        """False if we're sure this shape will not paint. True if it *might* paint."""

        def _visible(fill, opacity):
            return fill != "none" and opacity != 0
            # we're ignoring fill-opacity

        # if all you do is move the pen around you can't draw
        if all(c[0].upper() == "M" for c in self.as_cmd_seq()):
            return False

        return _visible(self.stroke, self.stroke_opacity) or _visible(
            self.fill, self.opacity
        )

    def bounding_box(self) -> Rect:
        x1, y1, x2, y2 = svg_pathops.bounding_box(self.as_cmd_seq())
        return Rect(x1, y1, x2 - x1, y2 - y1)

    def apply_transform(self, transform: Affine2D) -> "SVGPath":
        target = self.as_path()
        if target is self:
            target = copy.deepcopy(target)
        cmds = (("M", (0, 0)),)
        if not transform.is_degenerate():
            cmds = svg_pathops.transform(self.as_cmd_seq(), transform)
        return target.update_path(cmds, inplace=True)

    def as_path(self) -> "SVGPath":
        raise NotImplementedError("You should implement as_path")

    def as_cmd_seq(self) -> svg_meta.SVGCommandSeq:
        return (
            self.as_path()
            .explicit_lines()  # hHvV => lL
            .expand_shorthand(inplace=True)
            .absolute(inplace=True)
            .arcs_to_cubics(inplace=True)
        )

    def absolute(self, inplace=False) -> "SVGShape":
        """Returns equivalent path with only absolute commands."""
        # only meaningful for path, which overrides
        return self

    def stroke_commands(self, tolerance) -> Generator[svg_meta.SVGCommand, None, None]:
        return svg_pathops.stroke(
            self.as_cmd_seq(),
            self.stroke_linecap,
            self.stroke_linejoin,
            self.stroke_width,
            self.stroke_miterlimit,
            tolerance,
        )

    def apply_style_attribute(self, inplace=False) -> "SVGShape":
        """Converts inlined CSS in "style" attribute to equivalent SVG attributes.

        Unsupported attributes for which no corresponding field exists in SVGShape
        dataclass are kept as text in the "style" attribute.
        """
        target = self
        if not inplace:
            target = copy.deepcopy(self)
        if target.style:
            attr_types = {
                f.name.replace("_", "-"): f.type for f in dataclasses.fields(self)
            }
            raw_attrs = {}
            unparsed_style = svg_meta.parse_css_declarations(
                target.style, raw_attrs, property_names=attr_types.keys()
            )
            for attr_name, attr_value in raw_attrs.items():
                field_name = attr_name.replace("-", "_")
                field_value = attr_types[attr_name](attr_value)
                setattr(target, field_name, field_value)
            target.style = unparsed_style
        return target

    def round_floats(self, ndigits: int, inplace=False) -> "SVGShape":
        """Round all floats in SVGShape to given decimal digits."""
        target = self
        if not inplace:
            target = copy.deepcopy(self)
        for field in dataclasses.fields(target):
            field_value = getattr(self, field.name)
            if isinstance(field_value, float):
                setattr(target, field.name, round(field_value, ndigits))
        return target

    def almost_equals(self, other: "SVGShape", tolerance: int) -> bool:
        assert isinstance(other, SVGShape)
        return self.round_floats(tolerance) == other.round_floats(tolerance)


# https://www.w3.org/TR/SVG11/paths.html#PathElement
@dataclasses.dataclass
class SVGPath(SVGShape, svg_meta.SVGCommandSeq):
    d: str = ""

    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)

    def _add(self, path_snippet):
        if self.d:
            self.d += " "
        self.d += path_snippet

    def _add_cmd(self, cmd, *args):
        self._add(svg_meta.path_segment(cmd, *args))

    def M(self, *args):
        self._add_cmd("M", *args)

    def m(self, *args):
        self._add_cmd("m", *args)

    def _arc(self, c, rx, ry, x, y, large_arc):
        self._add(svg_meta.path_segment(c, rx, ry, 0, large_arc, 1, x, y))

    def A(self, rx, ry, x, y, large_arc=0):
        self._arc("A", rx, ry, x, y, large_arc)

    def a(self, rx, ry, x, y, large_arc=0):
        self._arc("a", rx, ry, x, y, large_arc)

    def H(self, *args):
        self._add_cmd("H", *args)

    def h(self, *args):
        self._add_cmd("h", *args)

    def V(self, *args):
        self._add_cmd("V", *args)

    def v(self, *args):
        self._add_cmd("v", *args)

    def L(self, *args):
        self._add_cmd("L", *args)

    def l(self, *args):
        self._add_cmd("L", *args)

    def C(self, *args):
        self._add_cmd("C", *args)

    def Q(self, *args):
        self._add_cmd("Q", *args)

    def end(self):
        self._add("Z")

    def as_path(self) -> "SVGPath":
        return self

    def remove_overlaps(self, inplace=False) -> "SVGPath":
        cmds = svg_pathops.remove_overlaps(self.as_cmd_seq(), fill_rule=self.fill_rule)
        target = self
        if not inplace:
            target = copy.deepcopy(self)
        # simplified paths follow the 'nonzero' winding rule
        target.fill_rule = target.clip_rule = "nonzero"
        return target.update_path(cmds, inplace=True)

    def __iter__(self):
        return parse_svg_path(self.d, exploded=True)

    def walk(self, callback):
        """Walk path and call callback to build potentially new commands.

        https://www.w3.org/TR/SVG11/paths.html

        def callback(subpath_start, curr_xy, cmd, args, prev_xy, prev_cmd, prev_args)
          prev_* None if there was no previous
          returns sequence of (new_cmd, new_args) that replace cmd, args
        """
        curr_pos = Point()
        subpath_start_pos = curr_pos  # where a z will take you
        new_cmds = []

        # iteration gives us exploded commands
        for idx, (cmd, args) in enumerate(self):
            svg_meta.check_cmd(cmd, args)
            if idx == 0 and cmd == "m":
                cmd = "M"

            prev = (None, None, None)
            if new_cmds:
                prev = new_cmds[-1]
            for (new_cmd, new_cmd_args) in callback(
                subpath_start_pos, curr_pos, cmd, args, *prev
            ):
                if new_cmd.lower() != "z":
                    next_pos = _next_pos(curr_pos, new_cmd, new_cmd_args)
                else:
                    next_pos = subpath_start_pos

                prev_pos, curr_pos = curr_pos, next_pos
                if new_cmd.upper() == "M":
                    subpath_start_pos = curr_pos
                new_cmds.append((prev_pos, new_cmd, new_cmd_args))

        self.d = ""
        for _, cmd, args in new_cmds:
            self._add_cmd(cmd, *args)

    def move(self, dx, dy, inplace=False):
        """Returns a new path that is this one shifted."""

        def move_callback(subpath_start, curr_pos, cmd, args, *_unused):
            del subpath_start
            del curr_pos
            # Paths must start with an absolute moveto. Relative bits are ... relative.
            # Shift the absolute parts and call it a day.
            if cmd.islower():
                return ((cmd, args),)
            x_coord_idxs, y_coord_idxs = svg_meta.cmd_coords(cmd)
            args = list(args)  # we'd like to mutate 'em
            for x_coord_idx in x_coord_idxs:
                args[x_coord_idx] += dx
            for y_coord_idx in y_coord_idxs:
                args[y_coord_idx] += dy
            return ((cmd, args),)

        target = self
        if not inplace:
            target = copy.deepcopy(self)
        target.walk(move_callback)
        return target

    def absolute(self, inplace=False) -> "SVGPath":
        """Returns equivalent path with only absolute commands."""

        def absolute_callback(subpath_start, curr_pos, cmd, args, *_):
            new_cmd, new_cmd_args = _relative_to_absolute(curr_pos, cmd, args)

            # if we modified cmd to pass *very* close to subpath start snap to it
            # eliminates issues with not-quite-closed shapes due float imprecision
            next_pos = _next_pos(curr_pos, new_cmd, new_cmd_args)
            if next_pos != subpath_start and next_pos.almost_equals(subpath_start):
                new_cmd, new_cmd_args = _move_endpoint(
                    curr_pos, new_cmd, new_cmd_args, subpath_start
                )
            return ((new_cmd, new_cmd_args),)

        target = self
        if not inplace:
            target = copy.deepcopy(self)
        target.walk(absolute_callback)
        return target

    def explicit_lines(self, inplace=False):
        """Replace all vertical/horizontal lines with line to (x,y)."""
        target = self
        if not inplace:
            target = copy.deepcopy(self)
        target.walk(_explicit_lines_callback)
        return target

    def expand_shorthand(self, inplace=False):
        """Rewrite commands that imply knowledge of prior commands arguments.

        In particular, shorthand quadratic and bezier curves become explicit.

        See https://www.w3.org/TR/SVG11/paths.html#PathDataCurveCommands.
        """

        def expand_shorthand_callback(
            _, curr_pos, cmd, args, prev_pos, prev_cmd, prev_args
        ):
            short_to_long = {"S": "C", "T": "Q"}
            if not cmd.upper() in short_to_long:
                return ((cmd, args),)

            if cmd.islower():
                cmd, args = _relative_to_absolute(curr_pos, cmd, args)

            # if there is no prev, or a bad prev, control point coincident current
            new_cp = (curr_pos.x, curr_pos.y)
            if prev_cmd:
                if prev_cmd.islower():
                    prev_cmd, prev_args = _relative_to_absolute(
                        prev_pos, prev_cmd, prev_args
                    )
                if prev_cmd in short_to_long.values():
                    # reflect 2nd-last x,y pair over curr_pos and make it our first arg
                    prev_cp = Point(prev_args[-4], prev_args[-3])
                    new_cp = (2 * curr_pos.x - prev_cp.x, 2 * curr_pos.y - prev_cp.y)

            return ((short_to_long[cmd], new_cp + args),)

        target = self
        if not inplace:
            target = copy.deepcopy(self)
        target.walk(expand_shorthand_callback)
        return target

    def arcs_to_cubics(self, inplace=False):
        """Replace all arcs with similar cubics"""

        def arc_to_cubic_callback(subpath_start, curr_pos, cmd, args, *_):
            del subpath_start
            if cmd not in {"a", "A"}:
                # no work to do
                return ((cmd, args),)

            (rx, ry, x_rotation, large, sweep, end_x, end_y) = args

            if cmd == "a":
                end_x += curr_pos.x
                end_y += curr_pos.y
            end_pt = Point(end_x, end_y)

            result = []
            for p1, p2, target in arc_to_cubic(
                curr_pos, rx, ry, x_rotation, large, sweep, end_pt
            ):
                x, y = target
                if p1 is not None:
                    assert p2 is not None
                    x1, y1 = p1
                    x2, y2 = p2
                    result.append(("C", (x1, y1, x2, y2, x, y)))
                else:
                    result.append(("L", (x, y)))

            return tuple(result)

        target = self
        if not inplace:
            target = copy.deepcopy(self)
        target.walk(arc_to_cubic_callback)
        return target

    @classmethod
    def from_commands(
        cls, svg_cmds: Generator[svg_meta.SVGCommand, None, None]
    ) -> "SVGPath":
        return cls().update_path(svg_cmds, inplace=True)

    def update_path(
        self, svg_cmds: Generator[svg_meta.SVGCommand, None, None], inplace=False
    ) -> "SVGPath":
        target = self
        if not inplace:
            target = copy.deepcopy(self)
        target.d = ""

        for cmd, args in svg_cmds:
            target._add_cmd(cmd, *args)
        return target

    def round_floats(self, ndigits: int, inplace=False) -> "SVGPath":
        """Round all floats in SVGPath to given decimal digits.

        Also reformat the SVGPath.d string floats with the same rounding.
        """
        target: SVGPath = super().round_floats(ndigits, inplace=inplace)

        d, target.d = target.d, ""
        for cmd, args in parse_svg_path(d):
            target._add_cmd(cmd, *(round(n, ndigits) for n in args))

        return target


# https://www.w3.org/TR/SVG11/shapes.html#CircleElement
@dataclasses.dataclass
class SVGCircle(SVGShape):
    r: float = 0
    cx: float = 0
    cy: float = 0

    def as_path(self) -> SVGPath:
        *shape_fields, r, cx, cy = dataclasses.astuple(self)
        path = SVGEllipse(rx=r, ry=r, cx=cx, cy=cy).as_path()
        path._copy_common_fields(*shape_fields)
        return path


# https://www.w3.org/TR/SVG11/shapes.html#EllipseElement
@dataclasses.dataclass
class SVGEllipse(SVGShape):
    rx: float = 0
    ry: float = 0
    cx: float = 0
    cy: float = 0

    def as_path(self) -> SVGPath:
        *shape_fields, rx, ry, cx, cy = dataclasses.astuple(self)
        path = SVGPath()
        # arc doesn't seem to like being a complete shape, draw two halves
        path.M(cx - rx, cy)
        path.A(rx, ry, cx + rx, cy, large_arc=1)
        path.A(rx, ry, cx - rx, cy, large_arc=1)
        path.end()
        path._copy_common_fields(*shape_fields)
        return path


# https://www.w3.org/TR/SVG11/shapes.html#LineElement
@dataclasses.dataclass
class SVGLine(SVGShape):
    x1: float = 0
    y1: float = 0
    x2: float = 0
    y2: float = 0

    def as_path(self) -> SVGPath:
        *shape_fields, x1, y1, x2, y2 = dataclasses.astuple(self)
        path = SVGPath()
        path.M(x1, y1)
        path.L(x2, y2)
        path._copy_common_fields(*shape_fields)
        return path


# https://www.w3.org/TR/SVG11/shapes.html#PolygonElement
@dataclasses.dataclass
class SVGPolygon(SVGShape):
    points: str = ""

    def as_path(self) -> SVGPath:
        *shape_fields, points = dataclasses.astuple(self)
        if self.points:
            path = SVGPath(d="M" + self.points + " Z")
        else:
            path = SVGPath()
        path._copy_common_fields(*shape_fields)
        return path


# https://www.w3.org/TR/SVG11/shapes.html#PolylineElement
@dataclasses.dataclass
class SVGPolyline(SVGShape):
    points: str = ""

    def as_path(self) -> SVGPath:
        *shape_fields, points = dataclasses.astuple(self)
        if points:
            path = SVGPath(d="M" + self.points)
        else:
            path = SVGPath()
        path._copy_common_fields(*shape_fields)
        return path


# https://www.w3.org/TR/SVG11/shapes.html#RectElement
@dataclasses.dataclass
class SVGRect(SVGShape):
    x: float = 0
    y: float = 0
    width: float = 0
    height: float = 0
    rx: float = 0
    ry: float = 0

    def __post_init__(self):
        if not self.rx:
            self.rx = self.ry
        if not self.ry:
            self.ry = self.rx
        self.rx = min(self.rx, self.width / 2)
        self.ry = min(self.ry, self.height / 2)

    def as_path(self) -> SVGPath:
        *shape_fields, x, y, w, h, rx, ry = dataclasses.astuple(self)
        path = SVGPath()
        path.M(x + rx, y)
        path.H(x + w - rx)
        if rx > 0:
            path.A(rx, ry, x + w, y + ry)
        path.V(y + h - ry)
        if rx > 0:
            path.A(rx, ry, x + w - rx, y + h)
        path.H(x + rx)
        if rx > 0:
            path.A(rx, ry, x, y + h - ry)
        path.V(y + ry)
        if rx > 0:
            path.A(rx, ry, x + rx, y)
        path.end()
        path._copy_common_fields(*shape_fields)

        return path


def union(shapes: Iterable[SVGShape]) -> SVGPath:
    return SVGPath.from_commands(
        svg_pathops.union(
            [s.as_cmd_seq() for s in shapes], [s.clip_rule for s in shapes]
        )
    )


def intersection(shapes: Iterable[SVGShape]) -> SVGPath:
    return SVGPath.from_commands(
        svg_pathops.intersection(
            [s.as_cmd_seq() for s in shapes], [s.clip_rule for s in shapes]
        )
    )

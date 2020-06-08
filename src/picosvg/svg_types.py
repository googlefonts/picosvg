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
from typing import Generator


# Subset of https://www.w3.org/TR/SVG11/painting.html
@dataclasses.dataclass
class SVGShape:
    id: str = ""
    clip_path: str = ""
    fill: str = "black"
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

    def _copy_common_fields(
        self,
        id,
        clip_path,
        fill,
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
    ):
        self.id = id
        self.clip_path = clip_path
        self.fill = fill
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

    def visible(self) -> bool:
        def _visible(fill, opacity):
            return fill != "none" and opacity != 0
            # we're ignoring fill-opacity

        return _visible(self.fill, self.opacity) or _visible(
            self.stroke, self.stroke_opacity
        )

    def bounding_box(self) -> Rect:
        x1, y1, x2, y2 = svg_pathops.bounding_box(self.as_cmd_seq())
        return Rect(x1, y1, x2 - x1, y2 - y1)

    def apply_transform(self, transform: Affine2D) -> "SVGPath":
        cmds = svg_pathops.transform(self.as_cmd_seq(), transform)
        return SVGPath.from_commands(cmds)

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

    def end(self):
        self._add("z")

    def as_path(self) -> "SVGPath":
        return self

    def __iter__(self):
        return parse_svg_path(self.d, exploded=True)

    def walk(self, callback):
        """Walk path and call callback to build potentially new commands.

        https://www.w3.org/TR/SVG11/paths.html

        def callback(curr_xy, cmd, args, prev_xy, prev_cmd, prev_args)
          prev_* None if there was no previous
          returns sequence of (new_cmd, new_args) that replace cmd, args
        """
        curr_pos = Point()
        new_cmds = []

        # iteration gives us exploded commands
        for idx, (cmd, args) in enumerate(self):
            svg_meta.check_cmd(cmd, args)
            if idx == 0 and cmd == "m":
                cmd = "M"

            prev = (None, None, None)
            if new_cmds:
                prev = new_cmds[-1]
            for (new_cmd, new_cmd_args) in callback(curr_pos, cmd, args, *prev):
                # update current position
                x_coord_idxs, y_coord_idxs = svg_meta.cmd_coords(new_cmd)
                new_x = curr_pos.x
                new_y = curr_pos.y
                if new_cmd.isupper():
                    if x_coord_idxs:
                        new_x = 0
                    if y_coord_idxs:
                        new_y = 0

                if x_coord_idxs:
                    new_x += new_cmd_args[x_coord_idxs[-1]]
                if y_coord_idxs:
                    new_y += new_cmd_args[y_coord_idxs[-1]]

                prev_pos = copy.copy(curr_pos)
                curr_pos = Point(new_x, new_y)
                new_cmds.append((prev_pos, new_cmd, new_cmd_args))

        self.d = ""
        for _, cmd, args in new_cmds:
            self._add_cmd(cmd, *args)

    # TODO replace with a proper transform
    def move(self, dx, dy, inplace=False):
        """Returns a new path that is this one shifted."""

        def move_callback(_, cmd, args, *_unused):
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

    @staticmethod
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

    def absolute(self, inplace=False) -> "SVGPath":
        """Returns equivalent path with only absolute commands."""

        def absolute_callback(curr_pos, cmd, args, *_):
            return (SVGPath._relative_to_absolute(curr_pos, cmd, args),)

        target = self
        if not inplace:
            target = copy.deepcopy(self)
        target.walk(absolute_callback)
        return target

    def explicit_lines(self, inplace=False):
        """Replace all vertical/horizontal lines with line to (x,y)."""

        def explicit_line_callback(curr_pos, cmd, args, *_):
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

        target = self
        if not inplace:
            target = copy.deepcopy(self)
        target.walk(explicit_line_callback)
        return target

    def expand_shorthand(self, inplace=False):
        """Rewrite commands that imply knowledge of prior commands arguments.

        In particular, shorthand quadratic and bezier curves become explicit.

        See https://www.w3.org/TR/SVG11/paths.html#PathDataCurveCommands.
        """

        def expand_shorthand_callback(
            curr_pos, cmd, args, prev_pos, prev_cmd, prev_args
        ):
            short_to_long = {"S": "C", "T": "Q"}
            if not cmd.upper() in short_to_long:
                return ((cmd, args),)

            if cmd.islower():
                cmd, args = SVGPath._relative_to_absolute(curr_pos, cmd, args)

            # if there is no prev, or a bad prev, control point coincident current
            new_cp = (curr_pos.x, curr_pos.y)
            if prev_cmd:
                if prev_cmd.islower():
                    prev_cmd, prev_args = SVGPath._relative_to_absolute(
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

        def arc_to_cubic_callback(curr_pos, cmd, args, *_):
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
        svg_path = cls()
        for cmd, args in svg_cmds:
            svg_path._add_cmd(cmd, *args)
        return svg_path


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
            path = SVGPath(d="M" + self.points + " z")
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

from arc_to_cubic import arc_to_cubic
import copy
import dataclasses
import svg_meta
from svg_path_iter import SVGPathIter

@dataclasses.dataclass
class Point:
  x: int = 0
  y: int = 0

# Subset of https://www.w3.org/TR/SVG11/painting.html
@dataclasses.dataclass
class SVGShape:
  clip_path: str = ''
  fill: str = ''
  stroke: str = ''

# https://www.w3.org/TR/SVG11/paths.html#PathElement
# Iterable, returning each command in the path.
@dataclasses.dataclass
class SVGPath(SVGShape):
  d: str = ''

  def __init__(self, **kwargs):
    for name, value in kwargs.items():
      setattr(self, name, value)

  def _add(self, path_snippet):
    if self.d:
        self.d += ' '
    self.d += path_snippet

  def _add_cmd(self, cmd, *args):
    self._add(svg_meta.path_segment(cmd, *args))

  def M(self, *args):
      self._add_cmd('M', *args)

  def m(self, *args):
      self._add_cmd('m', *args)

  def _arc(self, c, rx, ry, x, y, large_arc):
      self._add(svg_meta.path_segment(c, rx, ry,
                                      0, large_arc, 1,
                                      x, y))

  def A(self, rx, ry, x, y, large_arc=0):
      self._arc('A', rx, ry, x, y, large_arc)

  def a(self, rx, ry, x, y, large_arc=0):
      self._arc('a', rx, ry, x, y, large_arc)

  def H(self, *args):
      self._add_cmd('H', *args)

  def h(self, *args):
      self._add_cmd('h', *args)

  def V(self, *args):
      self._add_cmd('V', *args)

  def v(self, *args):
      self._add_cmd('v', *args)

  def L(self, *args):
      self._add_cmd('L', *args)

  def l(self, *args):
      self._add_cmd('L', *args)

  def end(self):
    self._add('z')

  def as_path(self) -> 'SVGPath':
    return self

  def element(self):
    return _data_to_el(self)

  def __iter__(self):
    return SVGPathIter(self.d, exploded=True)

  def walk(self, callback):
    """Walk path and call callback to build potentially new commands.

    def callback(curr_xy, cmd, args, prev_xy, prev_cmd, prev_args)
      prev_* None if there was no previous
      returns sequence of (new_cmd, new_args) that replace cmd, args
    """
    # https://www.w3.org/TR/SVG11/paths.html
    curr_pos = Point()
    new_cmds = []

    # iteration gives us exploded commands
    for idx, (cmd, args) in enumerate(self):
      svg_meta.check_cmd(cmd, args)
      if idx == 0 and cmd == 'm':
        cmd = 'M'

      prev = (None, None, None)
      if new_cmds:
        prev = new_cmds[-1]

      for (new_cmd, new_cmd_args) in callback(curr_pos, cmd, args, *prev):
        # update current position
        x_coord_idxs, y_coord_idxs = svg_meta.cmd_coords(new_cmd)
        if new_cmd.isupper():
          if x_coord_idxs:
            curr_pos.x = 0
          if y_coord_idxs:
            curr_pos.y = 0

        if x_coord_idxs:
          curr_pos.x += new_cmd_args[x_coord_idxs[-1]]
        if y_coord_idxs:
          curr_pos.y += new_cmd_args[y_coord_idxs[-1]]

        new_cmds.append((copy.copy(curr_pos), new_cmd, new_cmd_args))

    self.d = ''
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
      target = SVGPath(d=self.d, clip_path=self.clip_path)
    target.walk(move_callback)
    return target

  def _relative_to_absolute(curr_pos, cmd, args):
    x_coord_idxs, y_coord_idxs = svg_meta.cmd_coords(cmd)
    if cmd.islower():
      cmd = cmd.upper()
      args = list(args)  # we'd like to mutate 'em
      for x_coord_idx in x_coord_idxs:
        args[x_coord_idx] += curr_pos.x
      for y_coord_idx in y_coord_idxs:
        args[y_coord_idx] += curr_pos.y
    return ((cmd, args),)

  def absolute(self, inplace=False):
    """Returns equivalent path with only absolute commands."""
    def absolute_callback(curr_pos, cmd, args, *_):
      return SVGPath._relative_to_absolute(curr_pos, cmd, args)

    target = self
    if not inplace:
      target = SVGPath(self.d, self.clip_path)
    target.walk(absolute_callback)
    return target

  def explicit_lines(self, inplace=False):
    """Replace all vertical/horizontal lines with line to (x,y)."""
    def explicit_line_callback(curr_pos, cmd, args, *_):
      if cmd == 'v':
        args = (0, args[0])
      elif cmd == 'V':
        args = (curr_pos.x, args[0])
      elif cmd == 'h':
        args = (args[0], 0)
      elif cmd == 'H':
        args = (args[0], curr_pos.y)
      else:
        return ((cmd, args),)  # nothing changes

      if cmd.islower():
        cmd = 'l'
      else:
        cmd = 'L'

      return ((cmd, args),)

    target = self
    if not inplace:
      target = SVGPath(d=self.d, clip_path=self.clip_path)
    target.walk(explicit_line_callback)
    return target


  def arcs_to_cubics(self, inplace=False):
    """Replace all arcs with similar cubics"""
    def arc_to_cubic_callback(curr_pos, cmd, args, *_):
      if cmd not in {'a', 'A'}:
        # no work to do
        return ((cmd, args),)

      (rx, ry, x_rotation, large, sweep, end_x, end_y) = args
      start_pt = (curr_pos.x, curr_pos.y)

      if cmd == 'a':
        end_x += curr_pos[0]
        end_y += curr_pos[1]
      end_pt = (end_x, end_y)

      result = []
      for p1, p2, target in arc_to_cubic(start_pt, rx, ry, x_rotation, large, sweep, end_pt):
        x1, y1 = p1.real, p1.imag
        x2, y2 = p2.real, p2.imag
        x, y = target.real, target.imag
        result.append(('C', (x1, y1, x2, y2, x, y)))
      return tuple(result)

    target = self
    if not inplace:
      target = SVGPath(d=self.d, clip_path=self.clip_path)
    target.walk(arc_to_cubic_callback)
    return target

  def expand_shorthand(self, inplace=False):
    """Rewrite commands that imply knowledge of prior commands arguments.

    In particular, shorthand quadratic and bezier curves become explicit.

    See https://www.w3.org/TR/SVG11/paths.html#PathDataCurveCommands.
    """
    def expand_shorthand_callback(curr_pos, cmd, args,
                                  prev_pos, prev_cmd, prev_args):
      short_to_long = {
        'S': 'C',
        'T': 'Q'
      }
      if not cmd.upper() in short_to_long:
        return ((cmd, args),)
      if cmd.islower():
        cmd, args = SVGPath._relative_to_absolute(cmd, args)

      # reflect 2nd-last x,y pair over curr_pos and make it our first arg
      if prev_cmd and prev_cmd.upper() in short_to_long.values():
        prev_cp = Point(prev_args[-4], prev_args[-3])
        new_cp = (2 * curr_pos.x - prev_cp.x,
                  2 * curr_pos.y - prev_cp.y)
      else:
        # if there is no prev, or a bad prev, control point coincident current
        new_cp = (curr_pos.x, curr_pos.y)

      return ((short_to_long[cmd], new_cp + args),)

    target = self
    if not inplace:
      target = SVGPath(d=self.d, clip_path=self.clip_path)
    target.walk(expand_shorthand_callback)
    return target

# https://www.w3.org/TR/SVG11/shapes.html#CircleElement
@dataclasses.dataclass
class SVGCircle:
  r: float
  cx: float = 0
  cy: float = 0
  clip_path: str = ''

  def as_path(self) -> SVGPath:
    return SVGEllipse(self.r, self.r, self.cx, self.cy, self.clip_path).as_path()

  def element(self):
    return _data_to_el(self)

# https://www.w3.org/TR/SVG11/shapes.html#EllipseElement
@dataclasses.dataclass
class SVGEllipse:
  rx: float
  ry: float
  cx: float = 0
  cy: float = 0
  clip_path: str = ''

  def as_path(self) -> SVGPath:
    rx, ry, cx, cy, clip_path = dataclasses.astuple(self)
    path = SVGPath()
    # arc doesn't seem to like being a complete shape, draw two halves
    path.M(cx - rx, cy)
    path.A(rx, ry, cx + rx, cy, large_arc=1)
    path.A(rx, ry, cx - rx, cy, large_arc=1)
    path.clip_path = clip_path
    return path

  def element(self):
    return _data_to_el(self)

# https://www.w3.org/TR/SVG11/shapes.html#LineElement
@dataclasses.dataclass
class SVGLine:
  x1: float = 0
  y1: float = 0
  x2: float = 0
  y2: float = 0
  clip_path: str = ''

  def as_path(self) -> SVGPath:
    x1, y1, x2, y2, clip_path = dataclasses.astuple(self)
    path = SVGPath()
    path.M(x1, y1)
    path.L(x2, y2)
    path.clip_path = clip_path
    return path

  def element(self):
    return _data_to_el(self)

# https://www.w3.org/TR/SVG11/shapes.html#PolygonElement
@dataclasses.dataclass
class SVGPolygon:
  points: str
  clip_path: str = ''

  def as_path(self) -> SVGPath:
    if self.points:
      path = SVGPath(d='M' + self.points + ' z')
    else:
      path = SVGPath()
    path.clip_path = self.clip_path
    return path

  def element(self):
    return _data_to_el(self)

# https://www.w3.org/TR/SVG11/shapes.html#PolylineElement
@dataclasses.dataclass
class SVGPolyline:
  points: str
  clip_path: str = ''

  def as_path(self) -> SVGPath:
    if self.points:
      return SVGPath(d='M' + self.points)
    return SVGPath()

  def element(self):
    return _data_to_el(self)

# https://www.w3.org/TR/SVG11/shapes.html#RectElement
@dataclasses.dataclass
class SVGRect:
  x: float = 0
  y: float = 0
  width: float = 0
  height: float = 0
  rx: float = 0
  ry: float = 0
  clip_path: str = ''

  def __post_init__(self):
    if not self.rx:
      self.rx = self.ry
    if not self.ry:
      self.ry = self.rx
    self.rx = min(self.rx, self.width / 2)
    self.ry = min(self.ry, self.height / 2)

  def as_path(self) -> SVGPath:
    x, y, w, h, rx, ry, clip_path = dataclasses.astuple(self)
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
    path.clip_path = clip_path
    return path

  def element(self):
    return _data_to_el(self)

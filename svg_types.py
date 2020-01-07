import dataclasses
import svg_meta
from svg_path_iter import SVGPathIter

@dataclasses.dataclass
class Point:
  x: int = 0
  y: int = 0

# https://www.w3.org/TR/SVG11/paths.html#PathElement
# Iterable, returning each command in the path.
@dataclasses.dataclass
class SVGPath:
  d: str = ''
  clip_path: str = ''

  def __init__(self, d=''):
    self.d = d

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

  def _walk(self, callback):
    """Walking path and call callback to build new commands.

    def callback(curr_xy, cmd, args) -> (new_cmd, new_args)
    """
    # https://www.w3.org/TR/SVG11/paths.html
    curr_pos = Point()
    new_cmds = []

    # iteration gives us exploded commands
    for idx, (cmd, args) in enumerate(self):
      svg_meta.check_cmd(cmd, args)
      if idx == 0 and cmd == 'm':
        cmd = 'M'

      new_cmd, new_cmd_args = callback(curr_pos, cmd, args)
      new_cmds.append((new_cmd, new_cmd_args))

      # update current position based on possibly modified command
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

    self.d = ''
    for cmd, args in new_cmds:
      self._add_cmd(cmd, *args)

  # TODO replace with a proper transform
  def move(self, dx, dy, inplace=False):
    """Returns a new path that is this one shifted."""
    def move_callback(_, cmd, args):
      # Paths must start with an absolute moveto. Relative bits are ... relative.
      # Shift the absolute parts and call it a day.
      if cmd.islower():
        return cmd, args
      x_coord_idxs, y_coord_idxs = svg_meta.cmd_coords(cmd)
      args = list(args)  # we'd like to mutate 'em
      for x_coord_idx in x_coord_idxs:
        args[x_coord_idx] += dx
      for y_coord_idx in y_coord_idxs:
        args[y_coord_idx] += dy
      return cmd, args

    target = self
    if not inplace:
      target = SVGPath(self.d, self.clip_path)
    target._walk(move_callback)
    return target

  def absolute(self, inplace=False):
    """Returns equivalent path with only absolute commands."""
    def abs_callback(curr_pos, cmd, args):
      x_coord_idxs, y_coord_idxs = svg_meta.cmd_coords(cmd)
      if cmd.islower():
        cmd = cmd.upper()
        args = list(args)  # we'd like to mutate 'em
        for x_coord_idx in x_coord_idxs:
          args[x_coord_idx] += curr_pos.x
        for y_coord_idx in y_coord_idxs:
          args[y_coord_idx] += curr_pos.y
      return cmd, args

    target = self
    if not inplace:
      target = SVGPath(self.d, self.clip_path)
    target._walk(abs_callback)
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
      path = SVGPath('M' + self.points + ' z')
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
      return SVGPath('M' + self.points)
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

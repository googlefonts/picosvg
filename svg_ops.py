"""Non-lossy SVG manipulations.

Primarily intended to permit conversion of an SVG to a simplified form so
a program can operate on it.
"""

import copy
import dataclasses
from lxml import etree
import re

_SVG_NS = 'http://www.w3.org/2000/svg'

# https://www.w3.org/TR/SVG11/paths.html#PathData
_CMD_ARGS = {
  'm': 2,
  'z': 0,
  'l': 2,
  'h': 1,
  'v': 1,
  'c': 6,
  's': 4,
  'q': 4,
  't': 2,
  'a': 7,
}
_CMD_ARGS.update({k.upper(): v for k, v in _CMD_ARGS.items()})


# For each command iterable of x-coords and iterable of y-coords
# Helpful if you want to adjust them
_CMD_COORDS = {
  'm': ((0,), (1,)),
  'z': ((), ()),
  'l': ((0,), (1,)),
  'h': ((0,), ()),
  'v': ((), (0,)),
  'c': ((0, 2, 4), (1, 3, 5)),
  's': ((0, 2), (1, 3)),
  'q': ((0, 2), (1, 3)),
  't': ((0,), (1,)),
  'a': ((5,), (6,)),
}
_CMD_COORDS.update({k.upper(): v for k, v in _CMD_COORDS.items()})

_CMD_RE = re.compile(f'([{"".join(_CMD_ARGS.keys())}])')

# https://www.w3.org/TR/SVG11/paths.html#PathDataMovetoCommands
# If a moveto is followed by multiple pairs of coordinates,
# the subsequent pairs are treated as implicit lineto commands
_IMPLICIT_REPEAT_CMD = {
  'm': 'l',
  'M': 'L'
}

def _check_cmd(cmd, args):
  if not cmd in _CMD_ARGS:
    raise ValueError(f'Bad command {cmd}')
  cmd_args = _CMD_ARGS[cmd]
  if cmd_args == 0:
    if args:
      raise ValueError(f'{cmd} has no args, {len(args)} invalid')
  elif len(args) % cmd_args != 0:
    raise ValueError(f'{cmd} has sets of {cmd_args} args, {len(args)} invalid')
  return cmd_args

def _explode_cmd(args_per_cmd, cmd, args):
  cmds = []
  for i in range(len(args) // args_per_cmd):
    if i > 0:
      cmd = _IMPLICIT_REPEAT_CMD.get(cmd, cmd)
    cmds.append((cmd, tuple(args[i * args_per_cmd:(i + 1) * args_per_cmd])))
  return cmds


def _parse_svg_path(svg_path: str, exploded=False):
  """Parses an svg path to tuples of (cmd, (args))"""
  command_tuples = []
  parts = _CMD_RE.split(svg_path)[1:]
  for i in range(0, len(parts), 2):
    cmd = parts[i]
    args = []
    raw_args = [s for s in re.split(r'[, ]|(?=-)', parts[i + 1].strip()) if s]
    for raw_arg in raw_args:
      try:
        args.append(float(raw_arg))
      except ValueError as e:
        raise ValueError(f'Unable to parse {raw_arg} from "{cmd}{parts[i + 1]}"')
    args_per_cmd = _check_cmd(cmd, args)
    if args_per_cmd == 0 or not exploded:
      command_tuples.append((cmd, tuple(args)))
    else:
      command_tuples.extend(_explode_cmd(args_per_cmd, cmd, args))
  return command_tuples

def _ntos(n):
  # %f likes to add unnecessary 0's, %g isn't consistent about # decimals
  return ('%.3f' % n).rstrip('0').rstrip('.')

def _svg_path_segment(cmd, *args):
  # put commas between coords, spaces otherwise, author readability pref
  cmd_args = _check_cmd(cmd, args)
  args = [_ntos(a) for a in args]
  combined_args = []
  xy_coords = set(zip(*_CMD_COORDS[cmd]))
  i = 0
  while i < len(args):
    if (i, i+1) in xy_coords:
      combined_args.append(f'{args[i]},{args[i+1]}')
      i += 2
    else:
      combined_args.append(args[i])
      i += 1
  return cmd + ' '.join(combined_args)

class SVGPathIter:
  """Iterates commands, optionally in exploded form.

  Exploded means when params repeat each the command is reported as
  if multiplied. For example "M1,1 2,2 3,3" would report as three
  separate steps when exploded.
  """
  def __init__(self, path: str, exploded=False):
    self.cmds = _parse_svg_path(path, exploded=exploded)
    self.cmd_idx = -1

  def __iter__(self):
    return self

  def __next__(self):
    self.cmd_idx += 1
    if self.cmd_idx >= len(self.cmds):
      raise StopIteration()
    return self.cmds[self.cmd_idx]

@dataclasses.dataclass
class Point:
  x: int = 0
  y: int = 0

# https://www.w3.org/TR/SVG11/paths.html#PathElement
# Iterable, returning each command in the path.
@dataclasses.dataclass
class SVGPath:
  d: str = ''

  def __init__(self, d=''):
    self.d = d

  def _add(self, path_snippet):
    if self.d:
        self.d += ' '
    self.d += path_snippet

  def _add_cmd(self, cmd, *args):
    self._add(_svg_path_segment(cmd, *args))

  def M(self, *args):
      self._add_cmd('M', *args)

  def m(self, *args):
      self._add_cmd('m', *args)

  def _arc(self, c, rx, ry, x, y, large_arc):
      self._add('%s%s,%s 0 %d 1 %s,%s' % (c, _ntos(rx), _ntos(ry), large_arc,
                                          _ntos(x), _ntos(y)))

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

  def _new_by_walk(self, callback):
    """Build a new path by walking this one and calling callback.

    def callback(curr_xy, cmd, args) -> (new_cmd, new_args)
    """
    # https://www.w3.org/TR/SVG11/paths.html
    curr_pos = Point()
    new_cmds = []

    # iteration gives us exploded commands
    for idx, (cmd, args) in enumerate(self):
      _check_cmd(cmd, args)
      if idx == 0 and cmd == 'm':
        cmd = 'M'

      new_cmd, new_cmd_args = callback(curr_pos, cmd, args)
      new_cmds.append((new_cmd, new_cmd_args))

      # update current position based on possibly modified command
      x_coord_idxs, y_coord_idxs = _CMD_COORDS[new_cmd]
      if new_cmd.isupper():
        if x_coord_idxs:
          curr_pos.x = 0
        if y_coord_idxs:
          curr_pos.y = 0

      if x_coord_idxs:
        curr_pos.x += new_cmd_args[x_coord_idxs[-1]]
      if y_coord_idxs:
        curr_pos.y += new_cmd_args[y_coord_idxs[-1]]

    new_path = SVGPath()
    for cmd, args in new_cmds:
      new_path._add_cmd(cmd, *args)

    return new_path

  # TODO replace with a proper transform
  def move(self, dx, dy):
    """Returns a new path that is this one shifted."""
    def move_callback(_, cmd, args):
      # Paths must start with an absolute moveto. Relative bits are ... relative.
      # Shift the absolute parts and call it a day.
      if cmd.islower():
        return cmd, args
      x_coord_idxs, y_coord_idxs = _CMD_COORDS[cmd]
      args = list(args)  # we'd like to mutate 'em
      for x_coord_idx in x_coord_idxs:
        args[x_coord_idx] += dx
      for y_coord_idx in y_coord_idxs:
        args[y_coord_idx] += dy
      return cmd, args

    return self._new_by_walk(move_callback)

  def absolute(self):
    """Returns equivalent path with only absolute commands."""
    def abs_callback(curr_pos, cmd, args):
      x_coord_idxs, y_coord_idxs = _CMD_COORDS[cmd]
      if cmd.islower():
        cmd = cmd.upper()
        args = list(args)  # we'd like to mutate 'em
        for x_coord_idx in x_coord_idxs:
          args[x_coord_idx] += curr_pos.x
        for y_coord_idx in y_coord_idxs:
          args[y_coord_idx] += curr_pos.y
      return cmd, args

    return self._new_by_walk(abs_callback)

# https://www.w3.org/TR/SVG11/shapes.html#CircleElement
@dataclasses.dataclass
class SVGCircle:
  r: float
  cx: float = 0
  cy: float = 0

  def as_path(self) -> SVGPath:
    return SVGEllipse(self.r, self.r, self.cx, self.cy).as_path()

  def element(self):
    return _data_to_el(self)

# https://www.w3.org/TR/SVG11/shapes.html#EllipseElement
@dataclasses.dataclass
class SVGEllipse:
  rx: float
  ry: float
  cx: float = 0
  cy: float = 0

  def as_path(self) -> SVGPath:
    rx, ry, cx, cy = dataclasses.astuple(self)
    path = SVGPath()
    # arc doesn't seem to like being a complete shape, draw two halves
    path.M(cx - rx, cy)
    path.A(rx, ry, cx + rx, cy, large_arc=1)
    path.A(rx, ry, cx - rx, cy, large_arc=1)
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

  def as_path(self) -> SVGPath:
    x1, y1, x2, y2 = dataclasses.astuple(self)
    path = SVGPath()
    path.M(x1, y1)
    path.L(x2, y2)
    return path

  def element(self):
    return _data_to_el(self)

# https://www.w3.org/TR/SVG11/shapes.html#PolygonElement
@dataclasses.dataclass
class SVGPolygon:
  points: str

  def as_path(self) -> SVGPath:
    if self.points:
      return SVGPath('M' + self.points + ' z')
    return SVGPath()

  def element(self):
    return _data_to_el(self)

# https://www.w3.org/TR/SVG11/shapes.html#PolylineElement
@dataclasses.dataclass
class SVGPolyline:
  points: str

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

  def __post_init__(self):
    if not self.rx:
      self.rx = self.ry
    if not self.ry:
      self.ry = self.rx
    self.rx = min(self.rx, self.width / 2)
    self.ry = min(self.ry, self.height / 2)

  def as_path(self) -> SVGPath:
    x, y, w, h, rx, ry = dataclasses.astuple(self)
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
    return path

  def element(self):
    return _data_to_el(self)

_ELEMENT_CLASSES = {
  'circle': SVGCircle,
  'ellipse': SVGEllipse,
  'line': SVGLine,
  'path': SVGPath,
  'polygon': SVGPolygon,
  'polyline': SVGPolyline,
  'rect': SVGRect,
}
_CLASS_ELEMENTS = {v: f'{{{_SVG_NS}}}{k}' for k, v in _ELEMENT_CLASSES.items()}
_ELEMENT_CLASSES.update({f'{{{_SVG_NS}}}{k}': v for k, v in _ELEMENT_CLASSES.items()})

def _el_to_data(el):
  if el.tag not in _ELEMENT_CLASSES:
    raise ValueError(f'Bad tag <{el.tag}>')
  data_type = _ELEMENT_CLASSES[el.tag]
  args = {f.name: f.type(el.attrib[f.name])
          for f in dataclasses.fields(data_type)
          if f.name in el.attrib}
  return data_type(**args)

def _data_to_el(data_obj):
  el = etree.Element(_CLASS_ELEMENTS[type(data_obj)])
  for field_name, field_value in dataclasses.asdict(data_obj).items():
    el.attrib[field_name] = field_value
  return el

def _etree(svg_content, copy=True):
  if isinstance(svg_content, str) or isinstance(svg_content, bytes):
    svg_content = etree.fromstring(svg_content)
  elif copy:
    svg_content = copy.deepcopy(svg_content)
  return svg_content

def _apply_swaps(svg_root, swaps):
  for old_el, new_el in swaps:
    parent = old_el.getparent()
    old_el.getparent().replace(old_el, new_el)

def shape_to_path(shape):
  svg_root = _etree(shape, copy=False)
  data_obj = _el_to_data(svg_root)
  return data_obj.as_path()

def replace_shapes_with_paths(svg_root):
  """Converts all basic shapes to their equivalent path."""
  svg_root = _etree(svg_root)
  swaps = []
  for el in svg_root.iter('*'):
    if el.tag not in _ELEMENT_CLASSES:
      continue
    path = shape_to_path(el)
    new_el = _data_to_el(path)
    swaps.append((el, new_el))
  _apply_swaps(svg_root, swaps)
  return svg_root



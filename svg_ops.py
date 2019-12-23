"""Non-lossy SVG manipulations.

Primarily intended to permit conversion of an SVG to a simplified form so
a program can operate on it.
"""

import dataclasses
from lxml import etree

def _ntos(n):
  # %f likes to add unnecessary 0's, %g isn't consistent about # decimals
  return ('%.3f' % n).rstrip('0').rstrip('.')

# https://www.w3.org/TR/SVG11/paths.html#PathElement
@dataclasses.dataclass
class SVGPath:
  d: str = ''

  def _add(self, path_snippet):
    if self.d:
        self.d += ' '
    self.d += path_snippet

  def _move(self, c, x, y):
      self._add('%s%s,%s' % (c, _ntos(x), _ntos(y)))

  def M(self, x, y):
      self._move('M', x, y)

  def m(self, x, y):
      self._move('m', x, y)

  def _arc(self, c, rx, ry, x, y, large_arc):
      self._add('%s%s,%s 0 %d 1 %s,%s' % (c, _ntos(rx), _ntos(ry), large_arc,
                                          _ntos(x), _ntos(y)))

  def A(self, rx, ry, x, y, large_arc=0):
      self._arc('A', rx, ry, x, y, large_arc)

  def a(self, rx, ry, x, y, large_arc=0):
      self._arc('a', rx, ry, x, y, large_arc)

  def _vhline(self, c, x):
      self._add('%s%s' % (c, _ntos(x)))

  def H(self, x):
      self._vhline('H', x)

  def h(self, x):
      self._vhline('h', x)

  def V(self, y):
      self._vhline('V', y)

  def v(self, y):
      self._vhline('v', y)

  def _line(self, c, x, y):
      self._add('%s%s,%s' % (c, _ntos(x), _ntos(y)))

  def L(self, x, y):
      self._line('L', x, y)

  def l(self, x, y):
      self._line('l', x, y)

  def end(self):
    self._add('z')

  def as_path(self) -> 'SVGPath':
    return self

# https://www.w3.org/TR/SVG11/shapes.html#RectElement
@dataclasses.dataclass
class SVGRect:
  x: int = 0
  y: int = 0
  width: int = 0
  height: int = 0
  rx: int = 0
  ry: int = 0

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

# https://www.w3.org/TR/SVG11/shapes.html#LineElement
@dataclasses.dataclass
class SVGLine:
  x1: int = 0
  y1: int = 0
  x2: int = 0
  y2: int = 0

  def as_path(self) -> SVGPath:
    x1, y1, x2, y2 = dataclasses.astuple(self)
    path = SVGPath()
    path.M(x1, y1)
    path.L(x2, y2)
    return path

_ELEMENT_CLASSES = {
  '{http://www.w3.org/2000/svg}line': SVGLine,
  '{http://www.w3.org/2000/svg}path': SVGPath,
  '{http://www.w3.org/2000/svg}rect': SVGRect,
}
_CLASS_ELEMENTS = {v: k for k, v in _ELEMENT_CLASSES.items()}

def _el_to_data(el):
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

def shape_to_path(svg_text):
  """Converts all shapes to an equivalent path."""
  swaps = []
  root = etree.fromstring(svg_text)
  for el in root.iter():
    if el.tag not in _ELEMENT_CLASSES:
      continue
    data_obj = _el_to_data(el)
    print(data_obj)
    path = data_obj.as_path()
    print(path)
    new_el = _data_to_el(path)
    print(etree.tostring(new_el))
    swaps.append((el, new_el))
  for old_el, new_el in swaps:
    parent = old_el.getparent()
    old_el.getparent().replace(old_el, new_el)
  return etree.tostring(root)

def absolute_paths(svg_text):
  """Makes all paths absolute."""
  svg_text



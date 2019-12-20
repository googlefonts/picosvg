"""Non-lossy SVG manipulations.

Primarily intended to permit conversion of an SVG to a simplified form so
a program can operate on it.
"""

import dataclasses
from lxml import etree

# https://www.w3.org/TR/SVG11/paths.html#PathElement
@dataclasses.dataclass
class SVGPath:
  d: str = ''

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
    return SVGPath()

_ELEMENT_CLASSES = {
  '{http://www.w3.org/2000/svg}rect': SVGRect,
  '{http://www.w3.org/2000/svg}path': SVGPath,
}
_CLASS_ELEMENTS = {v: k for k, v in _ELEMENT_CLASSES.items()}

def _el_to_data(el):
  data_type = _ELEMENT_CLASSES[el.tag]
  return data_type(f.type(el.attrib(f.name))
                   for f in dataclasses.fields(data_type)
                   if f.name in el.attrib)

def _data_to_el(data):
  el = etree.Element(_CLASS_ELEMENTS[type(data)])
  return el

def shape_to_path(svg_text):
  """Converts all shapes to an equivalent path."""
  swaps = []
  root = etree.fromstring(svg_text)
  for el in root.iter():
    if el.tag not in _ELEMENT_CLASSES:
      continue
    path = _el_to_data(el).as_path()
    swaps.append((el, _data_to_el(path)))
  for old_el, new_el in swaps:
    parent = old_el.getparent()
    old_el.getparent().replace(old_el, new_el)
  return etree.tostring(root, pretty_print=True)

def absolute_paths(svg_text):
  """Makes all paths absolute."""
  svg_text



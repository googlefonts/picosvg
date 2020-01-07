import copy
import dataclasses
from lxml import etree
import re
from svg_meta import svgns
import svg_pathops
from svg_types import *

_ELEMENT_CLASSES = {
  'circle': SVGCircle,
  'ellipse': SVGEllipse,
  'line': SVGLine,
  'path': SVGPath,
  'polygon': SVGPolygon,
  'polyline': SVGPolyline,
  'rect': SVGRect,
}
_CLASS_ELEMENTS = {v: f'{{{svgns()}}}{k}' for k, v in _ELEMENT_CLASSES.items()}
_ELEMENT_CLASSES.update({f'{{{svgns()}}}{k}': v for k, v in _ELEMENT_CLASSES.items()})

_OMIT_FIELD_IF_BLANK = { f.name for f in dataclasses.fields(SVGShape) }

_ATTR_RENAMES = {
  'clip-path': 'clip_path'
}
_FIELD_RENAMES = {v: k for k, v in _ATTR_RENAMES.items()}

def _el_to_data(el):
  if el.tag not in _ELEMENT_CLASSES:
    raise ValueError(f'Bad tag <{el.tag}>')
  data_type = _ELEMENT_CLASSES[el.tag]
  args = {f.name: f.type(el.attrib[_FIELD_RENAMES.get(f.name, f.name)])
          for f in dataclasses.fields(data_type)
          if _FIELD_RENAMES.get(f.name, f.name) in el.attrib}
  return data_type(**args)

def _data_to_el(data_obj):
  el = etree.Element(_CLASS_ELEMENTS[type(data_obj)])
  for field_name, field_value in dataclasses.asdict(data_obj).items():
    if field_name in _OMIT_FIELD_IF_BLANK and not field_value:
      continue
    print(f'Set {_FIELD_RENAMES.get(field_name, field_name)} = {field_value}')
    el.attrib[_FIELD_RENAMES.get(field_name, field_name)] = str(field_value)
  return el

def _apply_swaps(svg_root, swaps):
  for old_el, new_el in swaps:
    parent = old_el.getparent()
    old_el.getparent().replace(old_el, new_el)

def shape_to_path(shape):
  svg_root = _etree(shape, duplicate=False)
  data_obj = _el_to_data(svg_root)
  return data_obj.as_path()

class SVG:
  def __init__(self, svg_root):
    self.svg_root = svg_root
    self.elements = None

  def _elements(self):
    if self.elements:
      return self.elements
    elements = []
    for el in self.svg_root.iter('*'):
      if el.tag not in _ELEMENT_CLASSES:
        continue
      elements.append((el, _el_to_data(el)))
    self.elements = elements
    return self.elements

  def shapes(self):
    return tuple(s for (_, s) in self._elements())

  def shapes_to_paths(self, inplace=False):
    """Converts all basic shapes to their equivalent path."""
    if not inplace:
      svg = SVG(copy.deepcopy(self.svg_root))
      svg.shapes_to_paths(inplace=True)
      return svg

    swaps = []
    for idx, (el, shape) in enumerate(self._elements()):
      self.elements[idx] = (el, shape.as_path())
    return self

  def apply_clip_paths(self, inplace=False):
    """Apply clipping to shapes and remove the clip paths."""
    if not inplace:
      svg = SVG(copy.deepcopy(self.svg_root))
      svg.apply_clip_paths(inplace=True)
      return svg

    self._update_etree()

    # find elements with clip paths
    clips = []
    for idx, (el, shape) in enumerate(self._elements()):
      if not shape.clip_path:
        continue
      match = re.match(r'^url[(]#([^)]+)[)]$', shape.clip_path)
      if not match:
        raise ValueError(f'Unrecognized clip-path "{shape.clip_path}"')
      clip_path_id = match.group(1)
      xpath = f'//svg:clipPath[@id="{clip_path_id}"]'
      clip_path_els = self.svg_root.xpath(xpath, namespaces={'svg': svgns()})
      if len(clip_path_els) != 1:
        raise ValueError(f'Need exactly 1 match for {xpath}'
                         f', got {len(clip_path_els)}')
      clip_el = clip_path_els[0]
      # union all the shapes under the clipPath
      # TODO what if what was there was more complex?
      clip_path = svg_pathops.union([_el_to_data(el) for el in clip_el])
      clips.append((idx, clip_el, clip_path))

    # TODO handle inherited clipping
    # https://www.w3.org/TR/SVG11/masking.html#EstablishingANewClippingPath

    # apply clip path to target
    for el_idx, _, clip_path in clips:
      print(f'Clip {self.elements[el_idx][1]} with {clip_path}')


    # destroy the clip path elements
    # destroy clip path container if now empty

    return self

  def _update_etree(self):
    if not self.elements:
      return
    swaps = []
    for old_el, shape in self.elements:
      swaps.append((old_el, _data_to_el(shape)))
    for old_el, new_el in swaps:
      parent = old_el.getparent()
      old_el.getparent().replace(old_el, new_el)
    self.elements = None

  def toetree(self):
    self._update_etree()
    return copy.deepcopy(self.svg_root)

  def tostring(self):
    self._update_etree()
    return etree.tostring(self.svg_root)

  def fromstring(string):
    return SVG(etree.fromstring(string))

  def parse(file_or_path):
    return SVG(etree.parse(file_or_path))

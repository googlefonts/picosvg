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

def from_element(el):
  if el.tag not in _ELEMENT_CLASSES:
    raise ValueError(f'Bad tag <{el.tag}>')
  data_type = _ELEMENT_CLASSES[el.tag]
  args = {f.name: f.type(el.attrib[_FIELD_RENAMES.get(f.name, f.name)])
          for f in dataclasses.fields(data_type)
          if _FIELD_RENAMES.get(f.name, f.name) in el.attrib}
  return data_type(**args)

def to_element(data_obj):
  el = etree.Element(_CLASS_ELEMENTS[type(data_obj)])
  for field_name, field_value in dataclasses.asdict(data_obj).items():
    if field_name in _OMIT_FIELD_IF_BLANK and not field_value:
      continue
    el.attrib[_FIELD_RENAMES.get(field_name, field_name)] = str(field_value)
  return el

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
      elements.append((el, from_element(el)))
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

  def _xpath(self, xpath, el=None):
    if el is None:
      el = self.svg_root
    return el.xpath(xpath, namespaces={'svg': svgns()})

  def _xpath_one(self, xpath):
    els = self._xpath(xpath)
    if len(els) != 1:
      raise ValueError(f'Need exactly 1 match for {xpath}, got {len(els)}')
    return els[0]

  def _resolve_url(self, url, el_tag):
    match = re.match(r'^url[(]#([\w-]+)[)]$', url)
    if not match:
      raise ValueError(f'Unrecognized url "{url}"')
    return self._xpath_one(f'//svg:{el_tag}[@id="{match.group(1)}"]')

  def _resolve_use(self, scope_el):
    attrib_not_copied = {'x', 'y', 'width', 'height', 'xlink_href'}

    swaps = []

    for use_el in self._xpath('.//svg:use', el=scope_el):
      ref = use_el.attrib.get('xlink_href', '')
      if not ref.startswith('#'):
        raise ValueError('Only use #fragment supported')
      target = self._xpath_one(f'//svg:*[@id="{ref[1:]}"]')
      group = etree.Element('g')
      group.append(copy.deepcopy(target))

      use_x = use_el.attrib.get('x', 0)
      use_y = use_el.attrib.get('y', 0)
      if use_x != 0 or use_y != 0:
        group.attrib['transform'] = (group.attrib.get('transform', '') 
                                     + f' translate({use_x}, {use_y})').strip()

      for attr_name in use_el.attrib:
        if attr_name in attrib_not_copied:
          continue
        group.attrib[attr_name] = use_el.attrib[attr_name]

      swaps.append((use_el, group))

    for old_el, new_el in swaps:
      old_el.getparent().replace(old_el, new_el)

  def resolve_use(self, inplace=False):
    """Instantiate reused elements.

    https://www.w3.org/TR/SVG11/struct.html#UseElement"""
    if not inplace:
      svg = SVG(copy.deepcopy(self.svg_root))
      svg.resolve_use(inplace=True)
      return svg

    self._update_etree()
    self._resolve_use(self.svg_root)

  def _ungroup(self, scope_el):
    """Push anything in a group up out of it
    """
    groups = [e for e in self._xpath(f'.//g', scope_el)]
    for group in groups:
      # move groups children up
      for child in group:
        group.remove(child)
        group.addnext(child)

      # TODO apply group attributes
      if group.attrib:
        raise ValueError('Application of group attrs not implemented')

    for group in groups:
      if group.getparent() is not None:
        group.getparent().remove(group)

  def _clip_path(self, el):
    """Resolve clip path for element, including inherited clipping.

    None if there is no clipping.

    https://www.w3.org/TR/SVG11/masking.html#EstablishingANewClippingPath
    """
    clip_paths = []
    while el is not None:
      clip_url = el.attrib.get('clip-path', None)
      if clip_url:
        clip_path_el = self._resolve_url(clip_url, 'clipPath')
        self._resolve_use(clip_path_el)
        self._ungroup(clip_path_el)

        # union all the shapes under the clipPath
        # Fails if there are any non-shapes under clipPath
        clip_path = svg_pathops.union(*[from_element(e)
                                        for e in clip_path_el])
        clip_paths.append(clip_path)

      el = el.getparent()

    # multiple clip paths leave behind their intersection
    if len(clip_paths) > 1:
      return svg_pathops.intersection(*clip_paths)
    elif clip_paths:
      return clip_paths[0]
    return None

  def apply_clip_paths(self, inplace=False):
    """Apply clipping to shapes and remove the clip paths."""
    if not inplace:
      svg = SVG(copy.deepcopy(self.svg_root))
      svg.apply_clip_paths(inplace=True)
      return svg

    self._update_etree()

    # find elements with clip paths
    clips = []  # 2-tuples of element index, clip path to apply
    clip_path_els = []
    for idx, (el, shape) in enumerate(self._elements()):
      clip_path = self._clip_path(el)
      if not clip_path:
        continue
      clips.append((idx, clip_path))

    # apply clip path to target
    for el_idx, clip_path in clips:
      el, target = self.elements[el_idx]
      target = (target.as_path()
                .absolute(inplace=True))

      target.d = svg_pathops.intersection(target, clip_path).d
      target.clip_path = ''
      self.elements[el_idx] = (el, target)

    # destroy clip path elements
    for clip_path_el in self._xpath('//svg:clipPath'):
      clip_path_el.getparent().remove(clip_path_el)

    # destroy clip-path attributes
    for el in self._xpath('//svg:*[@clip-path]'):
      del el.attrib['clip-path']

    return self

  def _update_etree(self):
    if not self.elements:
      return
    swaps = []
    for old_el, shape in self.elements:
      swaps.append((old_el, to_element(shape)))
    for old_el, new_el in swaps:
      parent = old_el.getparent()
      old_el.getparent().replace(old_el, new_el)
    self.elements = None

  def toetree(self):
    self._update_etree()
    return copy.deepcopy(self.svg_root)

  def tostring(self):
    self._update_etree()
    return (etree.tostring(self.svg_root)
            .decode('utf-8')
            .replace('xlink_href', 'xlink:href'))

  @classmethod
  def fromstring(_, string):
    if isinstance(string, bytes):
      string = string.decode('utf-8')
    string = string.replace('xlink:href', 'xlink_href')
    return SVG(etree.fromstring(string))

  @classmethod
  def parse(_, file_or_path):
    if hasattr(file_or_path, 'read'):
      raw_svg = file_or_path.read()
    else:
      with open(file_or_path) as f:
        raw_svg = f.read()
    return SVG.fromstring(raw_svg)

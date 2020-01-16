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

      new_el = copy.deepcopy(target)

      group = etree.Element('g')
      use_x = use_el.attrib.get('x', 0)
      use_y = use_el.attrib.get('y', 0)
      if use_x != 0 or use_y != 0:
        group.attrib['transform'] = (group.attrib.get('transform', '') 
                                     + f' translate({use_x}, {use_y})').strip()

      for attr_name in use_el.attrib:
        if attr_name in attrib_not_copied:
          continue
        group.attrib[attr_name] = use_el.attrib[attr_name]

      if len(group.attrib):
        group.append(new_el)
        swaps.append((use_el, group))
      else:
        swaps.append((use_el, new_el))

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
    return self

  def _resolve_clip_path(self, clip_path_url):
    clip_path_el = self._resolve_url(clip_path_url, 'clipPath')
    self._resolve_use(clip_path_el)
    self._ungroup(clip_path_el)

    # union all the shapes under the clipPath
    # Fails if there are any non-shapes under clipPath
    clip_path = svg_pathops.union(*[from_element(e)
                                    for e in clip_path_el])
    return clip_path

  def _combine_clip_paths(self, clip_paths):
    # multiple clip paths leave behind their intersection
    if len(clip_paths) > 1:
      return svg_pathops.intersection(*clip_paths)
    elif clip_paths:
      return clip_paths[0]
    return None

  def _new_id(self, tag, template):
    for i in range(100):
      potential_id = template % i
      existing = self._xpath(f'//svg:{tag}[@id="{potential_id}"]')
      if not existing:
        return potential_id
    raise ValueError(f'No free id for {template}')

  def _ungroup(self, scope_el):
    """Push inherited attributes from group down, then remove the group.

    If result has multiple clip paths merge them.
    """
    groups = [e for e in self._xpath(f'.//svg:g', scope_el)]
    multi_clips = []
    for group in groups:
      # move groups children up
      for child in group:
        group.remove(child)
        group.addnext(child)

        #  apply group attributes
        if 'clip-path' in group.attrib:
          clips = sorted(child.attrib.get('clip-path', '').split(',')
                         + [group.attrib.get('clip-path')])
          child.attrib['clip-path'] = ','.join([c for c in clips if c])
          if ',' in child.attrib['clip-path']:
            multi_clips.append(child)

    # nuke the groups
    for group in groups:
      if group.getparent() is not None:
        group.getparent().remove(group)

    # if we have new combinations of clip paths materialize them
    new_clip_paths = {}
    old_clip_paths = []
    for clipped_el in multi_clips:
      clip_refs = clipped_el.attrib['clip-path']
      if clip_refs not in new_clip_paths:
        clip_ref_urls = clip_refs.split(',')
        old_clip_paths.extend([self._resolve_url(ref, 'clipPath')
                               for ref in clip_ref_urls])
        clip_paths = [self._resolve_clip_path(ref) for ref in clip_ref_urls]
        clip_path = self._combine_clip_paths(clip_paths)
        new_el = etree.SubElement(self.svg_root, 'clipPath')
        new_el.attrib['id'] = self._new_id('clipPath', 'merged-clip-%d')
        new_el.append(to_element(clip_path))
        new_clip_paths[clip_refs] = new_el

      new_ref_id = new_clip_paths[clip_refs].attrib['id']
      clipped_el.attrib['clip-path'] = f'url(#{new_ref_id})'

    # destroy unreferenced clip paths
    for old_clip_path in old_clip_paths:
      if old_clip_path.getparent() is None:
        continue
      old_id = old_clip_path.attrib['id']
      if not self._xpath(f'//svg:*[@clip-path="url(#{old_id})"]'):
        old_clip_path.getparent().remove(old_clip_path)

  def _compute_clip_path(self, el):
    """Resolve clip path for element, including inherited clipping.

    None if there is no clipping.

    https://www.w3.org/TR/SVG11/masking.html#EstablishingANewClippingPath
    """
    clip_paths = []
    while el is not None:
      clip_url = el.attrib.get('clip-path', None)
      if clip_url:
        clip_paths.append(self._resolve_clip_path(clip_url))
      el = el.getparent()

    return self._combine_clip_paths(clip_paths)

  def ungroup(self, inplace=False):
    if not inplace:
      svg = SVG(copy.deepcopy(self.svg_root))
      svg.ungroup(inplace=True)
      return svg

    self._update_etree()
    self._ungroup(self.svg_root)
    return self

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
      clip_path = self._compute_clip_path(el)
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

  def tonanosvg(self, inplace=False):
    if not inplace:
      svg = SVG(copy.deepcopy(self.svg_root))
      svg.tonanosvg(inplace=True)
      return svg

    self._update_etree()

    self.shapes_to_paths(inplace=True)
    self.resolve_use(inplace=True)
    self.apply_clip_paths(inplace=True)
    self.ungroup(inplace=True)

    # Collect gradients; remove other defs
    gradient_defs = etree.Element('defs')
    for gradient in self._xpath('//svg:linearGradient | //svg:radialGradient'):
      gradient.getparent().remove(gradient)
      gradient_defs.append(gradient)

    for def_el in [e for e in self._xpath('//svg:defs')]:
      def_el.getparent().remove(def_el)

    self.svg_root.insert(0, gradient_defs)

    # TODO check if we're a legal nanosvg, bail if not
    # TODO define what that means

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

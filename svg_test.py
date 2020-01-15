import dataclasses
from lxml import etree
import pytest
from svg import SVG

def svg_string(*els):
  root = etree.fromstring('<svg version="1.1" xmlns="http://www.w3.org/2000/svg"/>')
  for el in els:
    root.append(etree.fromstring(el))
  return etree.tostring(root)

def drop_whitespace(svg):
  svg._update_etree()
  for el in svg.svg_root.iter('*'):
    if el.text is not None:
      el.text = el.text.strip()
    if el.tail is not None:
      el.tail = el.tail.strip()

@pytest.mark.parametrize(
  "shape, expected_attrib",
  [
    # path
    (
      "<path d='M1,1 2,2' fill='blue' />",
      {
        'fill': 'blue',
      }
    )
  ]
)
def test_parse_common_attrib(shape, expected_attrib):
  svg = SVG.fromstring(shape)
  field_values = dataclasses.asdict(svg.shapes()[0])
  for attrib, expected_value in expected_attrib.items():
    assert field_values[attrib] == expected_value

# https://www.w3.org/TR/SVG11/shapes.html
@pytest.mark.parametrize(
  "shape, expected_path",
  [
  # path: direct passthrough
  (
    "<path d='I love kittens'/>",
    "I love kittens",
  ),
  # path no @d
  (
    "<path duck='Mallard'/>",
    '',
  ),
  # line
  (
    '<line x1="10" x2="50" y1="110" y2="150"/>',
    'M10,110 L50,150',
  ),
  # line, decimal positioning
  (
    '<line x1="10.0" x2="50.5" y1="110.2" y2="150.7"/>',
    'M10,110.2 L50.5,150.7',
  ),
  # rect: minimal valid example
  (
    "<rect width='1' height='1'/>",
    "M0,0 H1 V1 H0 V0 z",
  ),
  # rect: sharp corners
  (
    "<rect x='10' y='11' width='17' height='11'/>",
    "M10,11 H27 V22 H10 V11 z",
  ),
  # rect: round corners
  (
    "<rect x='9' y='9' width='11' height='7' rx='2'/>",
    "M11,9 H18 A2 2 0 0 1 20,11 V14 A2 2 0 0 1 18,16 H11"
    " A2 2 0 0 1 9,14 V11 A2 2 0 0 1 11,9 z",
  ),
  # rect: simple
  (
    "<rect x='11.5' y='16' width='11' height='2'/>",
    "M11.5,16 H22.5 V18 H11.5 V16 z",
  ),
  # polygon
  (
    "<polygon points='30,10 50,30 10,30'/>",
    "M30,10 50,30 10,30 z",
  ),
  # polyline
  (
    "<polyline points='30,10 50,30 10,30'/>",
    "M30,10 50,30 10,30",
  ),
  # circle, minimal valid example
  (
    "<circle r='1'/>",
    "M-1,0 A1 1 0 1 1 1,0 A1 1 0 1 1 -1,0",
  ),
  # circle
  (
    "<circle cx='600' cy='200' r='100'/>",
    "M500,200 A100 100 0 1 1 700,200 A100 100 0 1 1 500,200",
  ),
  # circle, decimal positioning
  (
    "<circle cx='12' cy='6.5' r='1.5'></circle>",
    "M10.5,6.5 A1.5 1.5 0 1 1 13.5,6.5 A1.5 1.5 0 1 1 10.5,6.5",
  ),
  # ellipse
  (
    '<ellipse cx="100" cy="50" rx="100" ry="50"/>',
    'M0,50 A100 50 0 1 1 200,50 A100 50 0 1 1 0,50',
  ),
  # ellipse, decimal positioning
  (
      '<ellipse cx="100.5" cy="50" rx="10" ry="50.5"/>',
      'M90.5,50 A10 50.5 0 1 1 110.5,50 A10 50.5 0 1 1 90.5,50',
  ),
  ]
)
def test_simple_replace_shapes_with_paths(shape: str, expected_path: str):
  actual = (SVG.fromstring(svg_string(shape))
            .shapes_to_paths(inplace=True)
            .tostring())
  expected_result = (SVG.fromstring(svg_string(f'<path d="{expected_path}"/>'))
                     .tostring())
  print(f'A: {actual}')
  print(f'E: {expected_result}')
  assert actual == expected_result

@pytest.mark.parametrize(
  "shape, expected_cmds",
  [
    # line
    (
      '<line x1="10" x2="50" y1="110" y2="150"/>',
      [
        ('M', (10., 110.)),
        ('L', (50., 150.)),
      ]
    ),
    # path explodes to show implicit commands
    (
      '<path d="m1,1 2,0 1,3"/>',
      [
        ('m', (1., 1.)),
        ('l', (2., 0.)),
        ('l', (1., 3.)),
      ]
    ),
    # vertical and horizontal movement
    (
      '<path d="m1,1 v2 h2z"/>',
      [
        ('m', (1., 1.)),
        ('v', (2.,)),
        ('h', (2.,)),
        ('z', ())
      ]
    ),
  ]
)
def test_iter(shape, expected_cmds):
  svg_path = (SVG.fromstring(svg_string(shape))
              .shapes_to_paths()
              .shapes()[0])
  actual_cmds = [t for t in svg_path]
  print(f'A: {actual_cmds}')
  print(f'E: {expected_cmds}')
  assert actual_cmds == expected_cmds

@pytest.mark.parametrize(
  "actual, expected_result",
  [
    ('clip-rect.svg', 'clip-rect-clipped.svg'),
    ('clip-ellipse.svg', 'clip-ellipse-clipped.svg'),
    ('clip-curves.svg', 'clip-curves-clipped.svg'),
    ('clip-multirect.svg', 'clip-multirect-clipped.svg'),
    ('clip-groups.svg', 'clip-groups-clipped.svg'),
  ]
)
def test_apply_clip_path(actual, expected_result):
  actual = SVG.parse(actual)
  expected_result = SVG.parse(expected_result)
  actual.apply_clip_paths(inplace=True)
  drop_whitespace(actual)
  drop_whitespace(expected_result)
  print(f'A: {actual.tostring()}')
  print(f'E: {expected_result.tostring()}')
  assert actual.tostring() == expected_result.tostring()

@pytest.mark.parametrize(
  "actual, expected_result",
  [
    ('use-ellipse.svg', 'use-ellipse-resolved.svg'),
  ]
)
def test_resolve_use(actual, expected_result):
  actual = SVG.parse(actual)
  expected_result = SVG.parse(expected_result)
  actual.resolve_use(inplace=True)
  drop_whitespace(actual)
  drop_whitespace(expected_result)
  print(f'A: {actual.tostring()}')
  print(f'E: {expected_result.tostring()}')
  assert actual.tostring() == expected_result.tostring()

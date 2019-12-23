from lxml import etree
import pytest
import svg_ops

def pretty_svg(el_or_text):
  if isinstance(el_or_text, bytes):
    el_or_text = etree.fromstring(el_or_text)
  return etree.tostring(el_or_text, pretty_print=True)

def svg(*els):
  parser = etree.XMLParser(remove_blank_text=True)
  root = etree.fromstring('<svg version="1.1" xmlns="http://www.w3.org/2000/svg"/>')
  for el in els:
    root.append(etree.fromstring(el))
  return etree.tostring(root)

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
    "M11,9 H18 A2,2 0 0 1 20,11 V14 A2,2 0 0 1 18,16 H11"
    " A2,2 0 0 1 9,14 V11 A2,2 0 0 1 11,9 z",
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
    "M-1,0 A1,1 0 1 1 1,0 A1,1 0 1 1 -1,0",
  ),
  # circle
  (
    "<circle cx='600' cy='200' r='100'/>",
    "M500,200 A100,100 0 1 1 700,200 A100,100 0 1 1 500,200",
  ),
  # circle, decimal positioning
  (
    "<circle cx='12' cy='6.5' r='1.5'></circle>",
    "M10.5,6.5 A1.5,1.5 0 1 1 13.5,6.5 A1.5,1.5 0 1 1 10.5,6.5",
  ),
  # ellipse
  (
    '<ellipse cx="100" cy="50" rx="100" ry="50"/>',
    'M0,50 A100,50 0 1 1 200,50 A100,50 0 1 1 0,50',
  ),
  # ellipse, decimal positioning
  (
      '<ellipse cx="100.5" cy="50" rx="10" ry="50.5"/>',
      'M90.5,50 A10,50.5 0 1 1 110.5,50 A10,50.5 0 1 1 90.5,50',
  ),
  ]
)
def test_simple_shape_to_path(capsys, shape: str, expected_path: str):
  actual = svg_ops.shape_to_path(svg(shape))
  expected_result = svg(f'<path d="{expected_path}"/>')
  print(f'A: {actual}')
  print(f'E: {expected_result}')
  assert actual == expected_result

# TODO handle transform, test



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

@pytest.mark.parametrize(
  "original, expected_result",
  [
    # line
    (
      svg('<line x1="10" x2="50" y1="110" y2="150"/>'),
      svg('<path d="M10,110 L50,150"/>'),
    ),
    # rect: minimal valid example
    (
        svg("<rect width='1' height='1'/>"),
        svg('<path d="M0,0 H1 V1 H0 V0 z"/>'),
    ),
  ]
)
def test_shape_to_path(capsys, original: str, expected_result: str):
  actual = svg_ops.shape_to_path(original)
  assert actual == expected_result

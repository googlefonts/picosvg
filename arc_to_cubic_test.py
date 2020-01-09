"""Adapted from FontTools ests/svgLib/path/parser_test.py.

Quick sanity check our minor changes give similar results to the original."""
from arc_to_cubic import arc_to_cubic
import pytest

def _uncomplex(*values):
  return tuple((round(v.real, 3), round(v.imag, 3)) for v in values)

@pytest.mark.parametrize(
  "arc, expected_curves",
  [
    (
      # Arc from 150,200 to 300, 50
      ((150, 200), 150, 150, 0, 1, 0, (300, 50)),
      # curves: point1, point2, target_point
      (
        (
            (150.0, 282.843),
            (217.157, 350.0),
            (300.0, 350.0)
        ),
        (
            (382.843, 350.0),
            (450.0, 282.843),
            (450.0, 200.0)
        ),
        (
            (450.0, 117.157),
            (382.843, 50.0),
            (300.0, 50.0)
        ),
      ),
    )
    # TODO test of degenerate arc
    # TODO test sweep, docs seemed to suggest it should reverse but ... not?
  ]
)
def test_parse_common_attrib(arc, expected_curves):
  actual_curves = tuple(_uncomplex(*t) for t in arc_to_cubic(*arc))
  print(f'A: {actual_curves}')
  print(f'E: {expected_curves}')
  assert actual_curves == expected_curves

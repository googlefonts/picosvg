import pytest
import svg_pathops
from svg_types import SVGPath, SVGRect

@pytest.mark.parametrize(
  "shape, expected_segments, expected_path",
  [
    # path
    (
      SVGPath(d='M1,1 2,2 z'),
      (
        ('moveTo', ((1., 1.),)),
        ('lineTo', ((2., 2.),)),
        ('closePath', ())
      ),
      'M1,1 L2,2 Z',
    ),
    # rect
    (
      SVGRect(x=4, y=4, width=6, height=16),
      (
        ('moveTo', ((4., 4.),)),
        ('lineTo', ((10., 4.),)),
        ('lineTo', ((10., 20.),)),
        ('lineTo', ((4., 20.),)),
        ('lineTo', ((4., 4.),)),
        ('closePath', ())
      ),
      'M4,4 L10,4 L10,20 L4,20 L4,4 Z',
    ),
  ]
)
def test_skia_path_roundtrip(shape, expected_segments, expected_path):
  skia_path = svg_pathops.skia_path(shape)
  assert tuple(skia_path.segments) == expected_segments
  assert svg_pathops.svg_path(skia_path).d == expected_path

@pytest.mark.parametrize(
  "shapes, expected_result",
  [
    # rect's
    (
      (SVGRect(x=4, y=4, width=6, height=6),
       SVGRect(x=6, y=6, width=6, height=6),),
      'M4,4 L10,4 L10,6 L12,6 L12,12 L6,12 L6,10 L4,10 Z',
    ),
  ]
)
def test_pathops_union(shapes, expected_result):
  assert svg_pathops.union(shapes).d == expected_result

@pytest.mark.parametrize(
  "shapes, expected_result",
  [
    # rect's
    (
      (SVGRect(x=4, y=4, width=6, height=6),
       SVGRect(x=6, y=6, width=6, height=6),),
      'M6,6 L10,6 L10,10 L6,10 L10,6 Z',
    ),
  ]
)
def test_pathops_intersection(shapes, expected_result):
  assert svg_pathops.intersection(shapes).d == expected_result

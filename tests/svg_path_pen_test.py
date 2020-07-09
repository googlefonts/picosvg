from picosvg.svg_transform import Affine2D
from picosvg.svg_types import SVGPath
from picosvg.svg_path_pen import SVGPathPen
import pytest


def test_draw_new_path():
    pen = SVGPathPen()

    pen.moveTo((0, 0))
    pen.lineTo((0, 10))
    pen.lineTo((10, 10))
    pen.lineTo((10, 0))
    pen.closePath()

    pen.moveTo((0, 15))
    pen.curveTo((0, 20), (10, 20), (10, 15))
    pen.closePath()

    pen.moveTo((0, -5))
    pen.qCurveTo((0, -8), (3, -10), (7, -10), (10, -8), (10, -5))
    pen.endPath()

    assert pen.path.d == (
        "M0,0 L0,10 L10,10 L10,0 Z "
        "M0,15 C0,20 10,20 10,15 Z "
        "M0,-5 Q0,-8 1.5,-9 Q3,-10 5,-10 Q7,-10 8.5,-9 Q10,-8 10,-5"
    )


def test_draw_onto_existing_path():
    path = SVGPath(d="M0,0 L0,10 L10,10 L10,0 Z")
    pen = SVGPathPen(path)

    pen.moveTo((0, 15))
    pen.lineTo((5, 20))
    pen.lineTo((10, 15))
    pen.closePath()

    assert path.d == "M0,0 L0,10 L10,10 L10,0 Z M0,15 L5,20 L10,15 Z"


def test_addComponent_raise_TypeError():
    pen = SVGPathPen()

    with pytest.raises(TypeError):
        pen.addComponent("b", Affine2D.identity())

import itertools
from typing import Optional
from picosvg.svg_types import SVGPath
from picosvg.svg_pathops import _qcurveto_to_svg


# NOTE: the FontTools Pens API uses camelCase for the method names


class SVGPathPen:
    """A FontTools Pen that draws onto a picosvg SVGPath.

    NOTE: The `addComponent` method is not supported and will raise TypeError.
    You should decompose components before drawing a UFO or TrueType glyph with the
    SVGPathPen (e.g.  using fontTools.recordingPen.DecomposingRecordingPen).

    Args:
        path: an existing SVGPath to extend with drawing commands. If None, a new
            SVGPath is created by default, accessible with the `path` attribute.
    """

    def __init__(self, path: Optional[SVGPath] = None):
        self.path = path or SVGPath()

    def moveTo(self, pt):
        self.path.M(*pt)

    def lineTo(self, pt):
        self.path.L(*pt)

    def curveTo(self, *points):
        # flatten sequence of point tuples
        self.path.C(*itertools.chain.from_iterable(points))

    def qCurveTo(self, *points):
        # handle TrueType quadratic splines with implicit on-curve mid-points
        for _, args in _qcurveto_to_svg(points):
            self.path.Q(*args)

    def closePath(self):
        self.path._add("Z")

    def endPath(self):
        pass

    def addComponent(self, glyphName, transformation):
        raise TypeError("Can't add component to SVGPath; should decompose it first")

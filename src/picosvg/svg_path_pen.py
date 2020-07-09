import itertools
from typing import Any, Mapping, Optional
from fontTools.pens.basePen import DecomposingPen
from picosvg.svg_types import SVGPath
from picosvg.svg_pathops import _qcurveto_to_svg


# NOTE: the FontTools Pens API uses camelCase for the method names


class SVGPathPen(DecomposingPen):
    """A FontTools Pen that draws onto a picosvg SVGPath.

    The pen automatically decomposes components using the provided `glyphSet`
    mapping.

    Args:
        glyphSet: a mapping of {glyph_name: glyph} to be used for resolving
            component references when the pen's `addComponent` method is called.
            (inherited from super-class). Can be set to empty dict if drawing
            simple contours without any components.
        path: an existing SVGPath to extend with drawing commands. If None, a new
            SVGPath is created by default, accessible with the `path` attribute.
    """

    # makes DecomposingPen raise 'KeyError' when component base is missing
    skipMissingComponents = False

    def __init__(
        self,
        glyphSet: Mapping[str, Any],
        path: Optional[SVGPath] = None,
    ):
        super().__init__(glyphSet)
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

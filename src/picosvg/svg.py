# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import defaultdict, deque
import copy
import dataclasses
from functools import reduce
import itertools
from lxml import etree  # pytype: disable=import-error
import re
from typing import (
    Any,
    Generator,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
)
from picosvg.svg_meta import (
    attrib_default,
    number_or_percentage,
    ntos,
    splitns,
    strip_ns,
    svgns,
    xlinkns,
    parse_css_declarations,
    parse_view_box,
    _LinkedDefault,
)
from picosvg.svg_types import *
from picosvg.svg_transform import Affine2D
import numbers

_SHAPE_CLASSES = {
    "circle": SVGCircle,
    "ellipse": SVGEllipse,
    "line": SVGLine,
    "path": SVGPath,
    "polygon": SVGPolygon,
    "polyline": SVGPolyline,
    "rect": SVGRect,
}
_GRADIENT_CLASSES = {
    "linearGradient": SVGLinearGradient,
    "radialGradient": SVGRadialGradient,
}
_CLASS_ELEMENTS = {
    v: f"{{{svgns()}}}{k}" for k, v in {**_SHAPE_CLASSES, **_GRADIENT_CLASSES}.items()
}
_SHAPE_CLASSES.update({f"{{{svgns()}}}{k}": v for k, v in _SHAPE_CLASSES.items()})

_SHAPE_FIELDS = {
    tag: tuple(f.name for f in dataclasses.fields(klass))
    for tag, klass in _SHAPE_CLASSES.items()
}
_GRADIENT_FIELDS = {
    tag: tuple(f.name for f in dataclasses.fields(klass))
    for tag, klass in _GRADIENT_CLASSES.items()
}
# Manually add stop, we don't type it
_GRADIENT_FIELDS["stop"] = tuple({"offset", "stop_color", "stop_opacity"})

_GRADIENT_COORDS = {
    "linearGradient": (("x1", "y1"), ("x2", "y2")),
    "radialGradient": (("cx", "cy"), ("fx", "fy")),
}

_VALID_FIELDS = {}
_VALID_FIELDS.update(_SHAPE_FIELDS)
_VALID_FIELDS.update(_GRADIENT_FIELDS)

_XLINK_TEMP = "xlink_"


_ATTRIB_W_CUSTOM_INHERITANCE = frozenset({"clip-path", "transform"})


# How much error, as pct of viewbox max(w,h), is allowed on lossy ops
# For example, for a Noto Emoji with a viewBox 0 0 128 128 permit error of 0.128
_MAX_PCT_ERROR = 0.1

# When you have no viewbox, use this. Absolute value in svg units.
_DEFAULT_DEFAULT_TOLERENCE = 0.1


# Rounding for rewritten gradient matrices
_GRADIENT_TRANSFORM_NDIGITS = 6


def _clamp(value: float, minv: float = 0.0, maxv: float = 1.0) -> float:
    return max(min(value, maxv), minv)


def _xlink_href_attr_name() -> str:
    return f"{{{xlinkns()}}}href"


def _copy_new_nsmap(tree, nsm):
    new_tree = etree.Element(tree.tag, nsmap=nsm)
    new_tree.attrib.update(tree.attrib)
    new_tree[:] = tree[:]
    return new_tree


def _fix_xlink_ns(tree):
    """Fix xlink namespace problems.

    If there are xlink temps, add namespace and fix temps.
    If we declare xlink but don't use it then remove it.
    """
    xlink_nsmap = {"xlink": xlinkns()}
    if "xlink" in tree.nsmap and not len(
        tree.xpath("//*[@xlink:href]", namespaces=xlink_nsmap)
    ):
        # no reason to keep xlink
        nsm = copy.copy(tree.nsmap)
        del nsm["xlink"]
        tree = _copy_new_nsmap(tree, nsm)

    elif "xlink" not in tree.nsmap and len(tree.xpath(f"//*[@{_XLINK_TEMP}]")):
        # declare xlink and fix temps
        nsm = copy.copy(tree.nsmap)
        nsm["xlink"] = xlinkns()
        tree = _copy_new_nsmap(tree, nsm)
        for el in tree.xpath(f"//*[@{_XLINK_TEMP}]"):
            # try to retain attrib order, unexpected when they shuffle
            attrs = [(k, v) for k, v in el.attrib.items()]
            el.attrib.clear()
            for name, value in attrs:
                if name == _XLINK_TEMP:
                    name = _xlink_href_attr_name()
                el.attrib[name] = value

    return tree


def _del_attrs(el, *attr_names):
    for name in attr_names:
        if name in el.attrib:
            del el.attrib[name]


def _attr_name(field_name: str) -> str:
    return field_name.replace("_", "-")


def _field_name(attr_name: str) -> str:
    return attr_name.replace("-", "_")


def _is_defs(tag):
    return strip_ns(tag) == "defs"


def _is_shape(tag):
    return strip_ns(tag) in _SHAPE_CLASSES


def _is_gradient(tag):
    return strip_ns(tag) in _GRADIENT_CLASSES


def _is_group(tag):
    return strip_ns(tag) == "g"


def _opacity(el: etree.Element) -> float:
    return _clamp(float(el.attrib.get("opacity", 1.0)))


def _is_removable_group(el):
    """
    Groups with:

        0 < opacity < 1
        >1 child

    must be retained.

    This over-retains groups; no difference unless children overlap
    """
    if not _is_group(el):
        return False
    # no attributes makes a group meaningless
    if len(el.attrib) == 0:
        return True
    num_children = sum(1 for e in el if e.tag is not etree.Comment)

    return num_children <= 1 or _opacity(el) in {0.0, 1.0}


def _try_remove_group(group_el, push_opacity=True):
    """
    Transfer children of group to their parent if possible.

    Only groups with 0 < opacity < 1 *and* multiple children must be retained.

    This over-retains groups; no difference unless children overlap
    """
    assert _is_group(group_el)

    remove = _is_removable_group(group_el)
    opacity = _opacity(group_el)
    if remove:
        children = list(group_el)
        if group_el.getparent() is not None:
            _replace_el(group_el, list(group_el))
        if push_opacity:
            for child in children:
                if child.tag is etree.Comment:
                    continue
                _inherit_attrib({"opacity": opacity}, child)
    else:
        # We're keeping the group, but we promised groups only have opacity
        group_el.attrib.clear()
        group_el.attrib["opacity"] = ntos(opacity)
        _drop_default_attrib(group_el.attrib)
    return remove


def _element_transform(el, current_transform=Affine2D.identity()):
    attr_name = "transform"
    if _is_gradient(el.tag):
        attr_name = "gradientTransform"

    raw = el.attrib.get(attr_name, None)
    if raw:
        return Affine2D.compose_ltr((Affine2D.fromstring(raw), current_transform))
    return current_transform


def from_element(el):
    if not _is_shape(el.tag):
        raise ValueError(f"Bad tag <{el.tag}>")
    data_type = _SHAPE_CLASSES[el.tag]
    parse_fn = getattr(data_type, "from_element", None)
    args = {
        f.name: f.type(el.attrib[_attr_name(f.name)])
        for f in dataclasses.fields(data_type)
        if el.attrib.get(_attr_name(f.name), "").strip()
    }
    return data_type(**args)


def to_element(data_obj):
    el = etree.Element(_CLASS_ELEMENTS[type(data_obj)])
    for field in dataclasses.fields(data_obj):
        field_value = getattr(data_obj, field.name)
        # omit attributes whose value == the respective default
        if isinstance(field.default, _LinkedDefault):
            default_value = field.default(data_obj)
        else:
            default_value = field.default
        if field_value == default_value:
            continue
        attrib_value = field_value
        if isinstance(attrib_value, numbers.Number):
            attrib_value = ntos(attrib_value)
        elif isinstance(attrib_value, Affine2D):
            attrib_value = attrib_value.tostring()
        el.attrib[_attr_name(field.name)] = attrib_value
    return el


def _reset_attrs(data_obj, field_pred):
    for field in dataclasses.fields(data_obj):
        if field_pred(field):
            setattr(data_obj, field.name, field.default)


def _safe_remove(el: etree.Element):
    parent = el.getparent()
    if parent is not None:
        parent.remove(el)


def _id_of_target(url):
    match = re.match(r"^url[(]#([\w-]+)[)]$", url)
    if not match:
        raise ValueError(f'Unrecognized url "{url}"')
    return match.group(1)


def _xpath_for_url(url, el_tag):
    return f'//svg:{el_tag}[@id="{_id_of_target(url)}"]'


def _attrib_to_pass_on(el, current_attrib, skips=_ATTRIB_W_CUSTOM_INHERITANCE):
    attr_catcher = etree.Element("dummy")
    _inherit_attrib(el.attrib, attr_catcher, skips=skips, skip_unhandled=True)
    _inherit_attrib(current_attrib, attr_catcher, skips=skips)
    return dict(attr_catcher.attrib)


def _replace_el(el, replacements):
    parent = el.getparent()
    idx = parent.index(el)
    parent.remove(el)
    for child_idx, child in enumerate(replacements):
        parent.insert(idx + child_idx, child)


class SVGTraverseContext(NamedTuple):
    nth_of_type: int
    element: etree.Element
    path: str
    transform: Affine2D
    clips: Tuple[SVGPath, ...]
    attrib: Mapping[str, Any]  # except _ATTRIB_W_CUSTOM_INHERITANCE

    def depth(self) -> int:
        return self.path.count("/") - 1

    def shape(self) -> SVGShape:
        return from_element(self.element)

    def is_shape(self):
        return _is_shape(self.element)

    def is_group(self):
        return _is_group(self.element)


class SVG:

    svg_root: etree.Element
    elements: List[Tuple[etree.Element, Tuple[SVGShape, ...]]]

    def __init__(self, svg_root):
        self.svg_root = svg_root
        self.elements = []

    def _elements(self) -> List[Tuple[etree.Element, Tuple[SVGShape, ...]]]:
        if self.elements:
            return self.elements
        elements = []
        view_box = self.view_box()
        for el in self.svg_root.iter("*"):
            if el.tag not in _SHAPE_CLASSES:
                continue
            elements.append((el, (from_element(el),)))
        self.elements = elements
        return self.elements

    def _set_element(self, idx: int, el: etree.Element, shapes: Tuple[SVGShape, ...]):
        self.elements[idx] = (el, shapes)

    def view_box(self) -> Optional[Rect]:
        if "viewBox" not in self.svg_root.attrib:
            # if there is no explicit viewbox try to use width/height
            w = self.svg_root.attrib.get("width", None)
            h = self.svg_root.attrib.get("height", None)
            if w and h:
                return Rect(0, 0, float(w), float(h))
            else:
                return None

        return parse_view_box(self.svg_root.attrib["viewBox"])

    def _default_tolerance(self):
        vbox = self.view_box()
        # Absence of viewBox is unusual
        if vbox is None:
            return _DEFAULT_DEFAULT_TOLERENCE
        return min(vbox.w, vbox.h) * _MAX_PCT_ERROR / 100

    @property
    def tolerance(self):
        return self._default_tolerance()

    def shapes(self):
        """Returns all shapes in order encountered.

        Use to operate per-shape; if you want to iterate over graph use breadth_first.
        """
        return tuple(shape for (_, shapes) in self._elements() for shape in shapes)

    def absolute(self, inplace=False):
        """Converts all basic shapes to their equivalent path."""
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.absolute(inplace=True)
            return svg

        swaps = []
        for idx, (el, (shape,)) in enumerate(self._elements()):
            self.elements[idx] = (el, (shape.absolute(),))
        return self

    def shapes_to_paths(self, inplace=False):
        """Converts all basic shapes to their equivalent path."""
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.shapes_to_paths(inplace=True)
            return svg

        swaps = []
        for idx, (el, (shape,)) in enumerate(self._elements()):
            self.elements[idx] = (el, (shape.as_path(),))
        return self

    def expand_shorthand(self, inplace=False):
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.expand_shorthand(inplace=True)
            return svg

        for idx, (el, (shape,)) in enumerate(self._elements()):
            if isinstance(shape, SVGPath):
                self.elements[idx] = (
                    el,
                    (shape.explicit_lines().expand_shorthand(inplace=True),),
                )
        return self

    def _apply_styles(self, el: etree.Element):
        parse_css_declarations(el.attrib.pop("style", ""), el.attrib)

    def apply_style_attributes(self, inplace=False):
        """Converts inlined CSS "style" attributes to equivalent SVG attributes."""
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.apply_style_attributes(inplace=True)
            return svg

        if self.elements:
            # if we already parsed the SVG shapes, apply style attrs and sync tree
            for shape in self.shapes():
                shape.apply_style_attribute(inplace=True)
            self._update_etree()

        # parse all remaining style attributes (e.g. in gradients or root svg element)
        for el in itertools.chain((self.svg_root,), self.xpath("//svg:*[@style]")):
            self._apply_styles(el)

        return self

    def xpath(self, xpath: str, el: etree.Element = None, expected_result_range=None):
        if el is None:
            el = self.svg_root
        results = el.xpath(xpath, namespaces={"svg": svgns()})
        if expected_result_range and len(results) not in expected_result_range:
            raise ValueError(
                f"Expected {xpath} matches in {expected_result_range}, {len(results)} results"
            )
        return results

    def xpath_one(self, xpath):
        return self.xpath(xpath, expected_result_range=range(1, 2))[0]

    def resolve_url(self, url, el_tag):
        return self.xpath_one(_xpath_for_url(url, el_tag))

    def _resolve_use(self, scope_el):
        attrib_not_copied = {
            "x",
            "y",
            "width",
            "height",
            "transform",
            _xlink_href_attr_name(),
        }

        # capture elements by id so even if we change it they remain stable
        el_by_id = {el.attrib["id"]: el for el in self.xpath(".//svg:*[@id]")}

        while True:
            swaps = []
            use_els = list(self.xpath(".//svg:use", el=scope_el))
            if not use_els:
                break
            for use_el in use_els:
                ref = use_el.attrib.get(_xlink_href_attr_name(), "")
                if not ref.startswith("#"):
                    raise ValueError(f"Only use #fragment supported, reject {ref}")

                target = el_by_id.get(ref[1:], None)
                if target is None:
                    raise ValueError(f"No element has id '{ref[1:]}'")

                new_el = copy.deepcopy(target)
                # leaving id's on <use> instantiated content is a path to duplicate ids
                for el in new_el.getiterator("*"):
                    if "id" in el.attrib:
                        del el.attrib["id"]

                group = etree.Element(f"{{{svgns()}}}g", nsmap=self.svg_root.nsmap)
                affine = Affine2D.identity().translate(
                    float(use_el.attrib.get("x", 0)), float(use_el.attrib.get("y", 0))
                )

                if "transform" in use_el.attrib:
                    affine = Affine2D.compose_ltr(
                        (
                            affine,
                            Affine2D.fromstring(use_el.attrib["transform"]),
                        )
                    )

                if affine != Affine2D.identity():
                    group.attrib["transform"] = affine.tostring()

                for attr_name in use_el.attrib:
                    if attr_name in attrib_not_copied:
                        continue
                    group.attrib[attr_name] = use_el.attrib[attr_name]

                group.append(new_el)

                if _try_remove_group(group, push_opacity=False):
                    _inherit_attrib(group.attrib, new_el)
                    swaps.append((use_el, new_el))
                else:
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
        return self

    def _resolve_clip_path(
        self, clip_path_url, transform=Affine2D.identity()
    ) -> SVGPath:
        clip_path_el = self.resolve_url(clip_path_url, "clipPath")
        self._resolve_use(clip_path_el)

        transform = _element_transform(clip_path_el, transform)
        clip_paths = [
            from_element(e).apply_transform(_element_transform(e, transform))
            for e in clip_path_el
        ]

        clip = SVGPath.from_commands(union(clip_paths))

        if "clip-path" in clip_path_el.attrib:
            # TODO cycle detection
            clip_clop = self._resolve_clip_path(
                clip_path_el.attrib["clip-path"], transform
            )
            clip = SVGPath.from_commands(intersection([clip, clip_clop]))

        return clip

    def append_to(self, xpath, el):
        self._update_etree()
        self.xpath_one(xpath).append(el)
        return el

    def _combine_clip_paths(self, clip_paths: Sequence[SVGPath]) -> SVGPath:
        # multiple clip paths leave behind their intersection
        if not clip_paths:
            raise ValueError("Cannot combine no clip_paths")
        if len(clip_paths) == 1:
            return clip_paths[0]
        return SVGPath.from_commands(intersection(clip_paths))

    def _new_id(self, template):
        for i in range(1 << 16):
            potential_id = template % i
            existing = self.xpath(f'//svg:*[@id="{potential_id}"]')
            if not existing:
                return potential_id
        raise ValueError(f"No free id for {template}")

    def _traverse(self, next_fn, append_fn):
        frontier = [
            SVGTraverseContext(
                0,
                self.svg_root,
                "/svg[0]",
                Affine2D.identity(),
                (),
                _attrib_to_pass_on(self.svg_root, {}),
            )
        ]
        while frontier:
            context = next_fn(frontier)
            yield context

            child_idxs = defaultdict(int)
            new_entries = []
            for child in context.element:
                if child.tag is etree.Comment:
                    continue
                transform = _element_transform(child, context.transform)
                clips = context.clips
                if "clip-path" in child.attrib:
                    clips += (
                        self._resolve_clip_path(child.attrib["clip-path"], transform),
                    )

                nth_of_type = child_idxs[strip_ns(child.tag)]
                child_idxs[strip_ns(child.tag)] += 1
                path = f"{context.path}/{strip_ns(child.tag)}[{nth_of_type}]"
                child_context = SVGTraverseContext(
                    nth_of_type,
                    child,
                    path,
                    transform,
                    clips,
                    _attrib_to_pass_on(child, context.attrib),
                )
                new_entries.append(child_context)
            append_fn(frontier, new_entries)

    def depth_first(self):
        # dfs will take from the back
        # reverse so this still yields in order (first child, second child, etc)
        # makes processing feel more intuitive
        yield from self._traverse(lambda f: f.pop(), lambda f, e: f.extend(reversed(e)))

    def breadth_first(self):
        yield from self._traverse(lambda f: f.pop(0), lambda f, e: f.extend(e))

    def _add_to_defs(self, defs, new_el):
        if "id" not in new_el.attrib:
            return  # idless defs are useless
        new_id = new_el.attrib["id"]
        insert_at = 0
        for i, el in enumerate(defs):
            if new_id < el.attrib["id"]:
                insert_at = i
                break
        defs.insert(insert_at, new_el)

    def _transformed_gradient(self, defs, fill_el, transform, shape_bbox):
        assert _is_gradient(fill_el), f"Not sure how to fill from {fill_el.tag}"

        gradient = (
            _GRADIENT_CLASSES[strip_ns(fill_el.tag)]
            .from_element(fill_el, self.view_box())
            .as_user_space_units(shape_bbox, inplace=True)
        )
        gradient.gradientTransform = Affine2D.compose_ltr(
            (gradient.gradientTransform, transform)
        ).round(_GRADIENT_TRANSFORM_NDIGITS)
        gradient.id = self._new_id(gradient.id + "_%d")

        new_fill = to_element(gradient)
        # TODO normalize stop elements too
        new_fill.extend(copy.deepcopy(stop) for stop in fill_el)

        self._apply_gradient_translation(new_fill)

        self._add_to_defs(defs, new_fill)
        return new_fill

    def _simplify(self):
        """
        Removes groups where possible, applies transforms, applies clip paths.
        """
        # Reversed: we want leaves first
        to_process = reversed(tuple(c for c in self.breadth_first()))

        defs = etree.Element(f"{{{svgns()}}}defs", nsmap=self.svg_root.nsmap)
        self.svg_root.insert(0, defs)

        for context in to_process:
            if "clipPath" in context.path:
                _safe_remove(context.element)
                continue

            el = context.element
            _del_attrs(el, *_ATTRIB_W_CUSTOM_INHERITANCE)  # handled separately

            skips = _ATTRIB_W_CUSTOM_INHERITANCE | {"opacity"}  # handled separately

            # context.attrib has already computed final values so it's fine to overwrite any current values
            _del_attrs(el, *(set(context.attrib) - skips))
            _inherit_attrib(context.attrib, el, skips=skips)

            # Only some elements change
            if _is_shape(el.tag):
                assert len(el) == 0, "Shapes shouldn't have children"

                # If we are transformed and we use a gradient we may need to
                # emit the transformed gradient
                if context.transform != Affine2D.identity() and "url" in el.attrib.get(
                    "fill", ""
                ):
                    fill_el = self.resolve_url(el.attrib["fill"], "*")
                    self._apply_gradient_template(fill_el)
                    fill_el = self._transformed_gradient(
                        defs,
                        fill_el,
                        context.transform,
                        from_element(el).bounding_box(),
                    )
                    fill_id = fill_el.attrib["id"]
                    el.attrib["fill"] = f"url(#{fill_id})"

                paths = [from_element(el).as_path().absolute(inplace=True)]
                initial_path = copy.deepcopy(paths[0])

                # stroke may introduce multiple paths
                assert len(paths) == 1  # oh ye of little faith
                if paths[0].stroke != "none":
                    paths = list(self._stroke(paths[0]))

                # Any remaining stroke attributes don't do anything
                # For example, a stroke-width with no stroke set is removed
                for path in paths:
                    _reset_attrs(path, lambda field: field.name.startswith("stroke"))

                # Apply any transform
                if context.transform != Affine2D.identity():
                    paths = [p.apply_transform(context.transform) for p in paths]

                if context.clips:
                    clip = SVGPath.from_commands(intersection(context.clips))
                    paths = [
                        p.update_path(intersection((p, clip)), inplace=True)
                        for p in paths
                    ]

                if len(paths) != 1 or paths[0] != initial_path:
                    _replace_el(el, [to_element(p) for p in paths])

            elif _is_gradient(el.tag):
                _safe_remove(el)
                self._add_to_defs(defs, el)
                self._apply_gradient_template(el)
                self._apply_gradient_translation(el)

            elif _is_defs(el.tag):
                # any children were already processed
                # now just moved to master defs
                for child_el in el:
                    self._add_to_defs(defs, child_el)
                _safe_remove(el)

            elif _is_group(el.tag):
                _try_remove_group(el)

        # https://github.com/googlefonts/nanoemoji/issues/275
        _del_attrs(self.svg_root, *_INHERITABLE_ATTRIB)

        self._remove_orphaned_gradients()

        # After simplification only gradient defs should be referenced
        # It's illegal for picosvg to leave anything else in defs
        for unused_el in [el for el in defs if not _is_gradient(el)]:
            defs.remove(unused_el)

        self.elements = None  # force elements to reload

    def simplify(self, inplace=False):
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.simplify(inplace=True)
            return svg

        self._update_etree()
        self._simplify()
        return self

    def _stroke(self, shape):
        """Convert stroke to path.

        Returns sequence of shapes in draw order. That is, result[1] should be
        drawn on top of result[0], etc."""

        assert shape.stroke != "none"

        # make a new path that is the stroke
        stroke = shape.as_path().update_path(shape.stroke_commands(self.tolerance))

        # skia stroker returns paths with 'nonzero' winding fill rule
        stroke.fill_rule = stroke.clip_rule = "nonzero"

        # a few attributes move in interesting ways
        stroke.opacity *= stroke.stroke_opacity
        stroke.fill = stroke.stroke
        # the fill and stroke are now different (filled) paths, reset 'fill_opacity'
        # to default and only use a combined 'opacity' in each one.
        shape.opacity *= shape.fill_opacity
        shape.fill_opacity = stroke.fill_opacity = 1.0

        # remove all the stroke settings
        for cleanmeup in (shape, stroke):
            _reset_attrs(cleanmeup, lambda field: field.name.startswith("stroke"))

        if not shape.might_paint():
            return (stroke,)

        # The original id doesn't correctly refer to either
        # It would be for the best if any id-based operations happened first
        shape.id = stroke.id = ""

        return (shape, stroke)

    def clip_to_viewbox(self, inplace=False):
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.clip_to_viewbox(inplace=True)
            return svg

        self._update_etree()

        view_box = self.view_box()

        # phase 1: dump shapes that are completely out of bounds
        for el, (shape,) in self._elements():
            if view_box.intersection(shape.bounding_box()) is None:
                _safe_remove(el)

        self.elements = None  # force elements to reload

        # phase 2: clip things that are partially out of bounds
        updates = []
        for idx, (el, (shape,)) in enumerate(self._elements()):
            bbox = shape.bounding_box()
            isct = view_box.intersection(bbox)
            assert isct is not None, f"We should have already dumped {shape}"
            if bbox == isct:
                continue
            clip_path = (
                SVGRect(x=isct.x, y=isct.y, width=isct.w, height=isct.h)
                .as_path()
                .absolute(inplace=True)
            )
            shape = shape.as_path().absolute(inplace=True)
            shape.update_path(intersection((shape, clip_path)), inplace=True)
            updates.append((idx, el, shape))

        for idx, el, shape in updates:
            self._set_element(idx, el, (shape,))

        # Update the etree
        self._update_etree()

        # We may now have useless groups
        for context in reversed(list(self.depth_first())):
            if _is_group(context.element):
                _try_remove_group(context.element)

        return self

    def evenodd_to_nonzero_winding(self, inplace=False):
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.evenodd_to_nonzero_winding(inplace=True)
            return svg

        for idx, (el, (shape,)) in enumerate(self._elements()):
            if shape.fill_rule == "evenodd":
                path = shape.as_path().remove_overlaps(inplace=True)
                self._set_element(idx, el, (path,))

        return self

    def round_floats(self, ndigits: int, inplace=False):
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.round_floats(ndigits, inplace=True)
            return svg

        for shape in self.shapes():
            shape.round_floats(ndigits, inplace=True)
        return self

    def remove_unpainted_shapes(self, inplace=False):
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.remove_unpainted_shapes(inplace=True)
            return svg

        self._update_etree()

        remove = []
        for (el, (shape,)) in self._elements():
            if not shape.might_paint():
                remove.append(el)

        for el in remove:
            el.getparent().remove(el)

        self.elements = None

        return self

    def remove_nonsvg_content(self, inplace=False):
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.remove_nonsvg_content(inplace=True)
            return svg

        self._update_etree()

        good_ns = {svgns(), xlinkns()}
        if self.svg_root.nsmap[None] == svgns():
            good_ns.add(None)

        el_to_rm = []
        for el in self.svg_root.getiterator("*"):
            attr_to_rm = []
            ns, _ = splitns(el.tag)
            if ns not in good_ns:
                el_to_rm.append(el)
                continue
            for attr in el.attrib:
                ns, _ = splitns(attr)
                if ns not in good_ns:
                    attr_to_rm.append(attr)
            for attr in attr_to_rm:
                del el.attrib[attr]

        for el in el_to_rm:
            el.getparent().remove(el)

        # Make svg default; destroy anything unexpected
        good_nsmap = {
            None: svgns(),
            "xlink": xlinkns(),
        }
        if any(good_nsmap.get(k, None) != v for k, v in self.svg_root.nsmap.items()):
            self.svg_root = _copy_new_nsmap(self.svg_root, good_nsmap)

        self.elements = None

        return self

    def remove_comments(self, inplace=False):
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.remove_comments(inplace=True)
            return svg

        self._update_etree()

        for el in self.xpath("//comment()"):
            el.getparent().remove(el)

        return self

    def remove_anonymous_symbols(self, inplace=False):
        # No id makes a symbol useless
        # https://github.com/googlefonts/picosvg/issues/46
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.remove_anonymous_symbols(inplace=True)
            return svg

        self._update_etree()

        for el in self.xpath("//svg:symbol[not(@id)]"):
            el.getparent().remove(el)

        return self

    def remove_title_meta_desc(self, inplace=False):
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.remove_title_meta_desc(inplace=True)
            return svg

        self._update_etree()

        for tag in ("title", "desc", "metadata", "comment"):
            for el in self.xpath(f"//svg:{tag}"):
                el.getparent().remove(el)

        return self

    def set_attributes(self, name_values, xpath="/svg:svg", inplace=False):
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.set_attributes(name_values, xpath=xpath, inplace=True)
            return svg

        self._update_etree()

        for el in self.xpath(xpath):
            for name, value in name_values:
                el.attrib[name] = value

        return self

    def remove_attributes(self, names, xpath="/svg:svg", inplace=False):
        """Drop things like viewBox, width, height that set size of overall svg"""
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.remove_attributes(names, xpath=xpath, inplace=True)
            return svg

        self._update_etree()

        for el in self.xpath(xpath):
            _del_attrs(el, *names)

        return self

    def normalize_opacity(self, inplace=False):
        """Merge '{fill,stroke}_opacity' with generic 'opacity' when possible."""
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.normalize_opacity(inplace=True)
            return svg

        for shape in self.shapes():
            shape.normalize_opacity(inplace=True)

        return self

    def _iter_nested_svgs(
        self, root: etree.Element
    ) -> Generator[etree.Element, None, None]:
        # This is different from Element.iter("svg") in that we don't yield the root
        # svg element itself, only traverse its children and yield any immediate
        # nested SVGs without traversing the latter's children as well.
        frontier = deque(root)
        while frontier:
            el = frontier.popleft()
            if el.tag is etree.Comment:
                continue
            if strip_ns(el.tag) == "svg":
                yield el
            elif len(el) != 0:
                frontier.extend(el)

    def _unnest_svg(
        self, svg: etree.Element, parent_width: float, parent_height: float
    ) -> Tuple[etree.Element, ...]:
        x = float(svg.attrib.get("x", 0))
        y = float(svg.attrib.get("y", 0))
        width = float(svg.attrib.get("width", parent_width))
        height = float(svg.attrib.get("height", parent_height))

        viewport = viewbox = Rect(x, y, width, height)
        if "viewBox" in svg.attrib:
            viewbox = parse_view_box(svg.attrib["viewBox"])

        # first recurse to un-nest any nested nested SVGs
        self._swap_elements(
            (el, self._unnest_svg(el, viewbox.w, viewbox.h))
            for el in self._iter_nested_svgs(svg)
        )

        g = etree.Element(f"{{{svgns()}}}g")
        g.extend(svg)

        if viewport != viewbox:
            preserve_aspect_ratio = svg.attrib.get("preserveAspectRatio", "xMidYMid")
            transform = Affine2D.rect_to_rect(viewbox, viewport, preserve_aspect_ratio)
        else:
            transform = Affine2D.identity().translate(x, y)

        if "transform" in svg.attrib:
            transform = Affine2D.compose_ltr(
                (transform, Affine2D.fromstring(svg.attrib["transform"]))
            )

        if transform != Affine2D.identity():
            g.attrib["transform"] = transform.tostring()

        # non-root svg elements by default have overflow="hidden" which means a clip path
        # the size of the SVG viewport is applied; if overflow="visible" don't clip
        # https://www.w3.org/TR/SVG/render.html#OverflowAndClipProperties
        overflow = svg.attrib.get("overflow", "hidden")
        if overflow == "visible":
            return (g,)

        if overflow != "hidden":
            raise NotImplementedError(f"overflow='{overflow}' is not supported")

        clip_path = etree.Element(
            f"{{{svgns()}}}clipPath", {"id": self._new_id("nested-svg-viewport-%d")}
        )
        clip_path.append(to_element(SVGRect(x=x, y=y, width=width, height=height)))
        clipped_g = etree.Element(f"{{{svgns()}}}g")
        clipped_g.attrib["clip-path"] = f"url(#{clip_path.attrib['id']})"
        clipped_g.append(g)

        return (clip_path, clipped_g)

    def resolve_nested_svgs(self, inplace=False):
        """Replace nested <svg> elements with equivalent <g> with a transform.

        NOTE: currently this is still missing two features:
        1) resolving percentage units in reference to the nearest SVG viewport;
        2) applying a clip to all children of the nested SVG with a rectangle the size
           of the new viewport (inner SVGs have default overflow property set to
           'hidden'). Blocked on https://github.com/googlefonts/picosvg/issues/200
        No error is raised in these cases.

        References:
        - https://www.w3.org/TR/SVG/coords.html
        - https://www.sarasoueidan.com/blog/nesting-svgs/
        """
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.resolve_nested_svgs(inplace=True)
            return svg

        self._update_etree()

        nested_svgs = list(self._iter_nested_svgs(self.svg_root))
        if len(nested_svgs) == 0:
            return

        vb = self.view_box()
        if vb is None:
            raise ValueError(
                "Can't determine root SVG width/height, "
                "which is required for resolving nested SVGs"
            )

        self._swap_elements(
            (el, self._unnest_svg(el, vb.w, vb.h)) for el in nested_svgs
        )

        return self

    def _select_gradients(self):
        return self.xpath(" | ".join(f"//svg:{tag}" for tag in _GRADIENT_CLASSES))

    def _apply_gradient_translation(self, el: etree.Element):
        assert _is_gradient(el)
        gradient = _GRADIENT_CLASSES[strip_ns(el.tag)].from_element(el, self.view_box())
        affine = gradient.gradientTransform

        # split translation from rest of the transform and apply to gradient coords
        translate, affine_prime = affine.decompose_translation()
        if translate.round(_GRADIENT_TRANSFORM_NDIGITS) != Affine2D.identity():
            for x_attr, y_attr in _GRADIENT_COORDS[strip_ns(el.tag)]:
                x = getattr(gradient, x_attr)
                y = getattr(gradient, y_attr)
                x_prime, y_prime = translate.map_point((x, y))
                setattr(gradient, x_attr, round(x_prime, _GRADIENT_TRANSFORM_NDIGITS))
                setattr(gradient, y_attr, round(y_prime, _GRADIENT_TRANSFORM_NDIGITS))

        gradient.gradientTransform = affine_prime.round(_GRADIENT_TRANSFORM_NDIGITS)

        el.attrib.clear()
        el.attrib.update(to_element(gradient).attrib)

    def _apply_gradient_template(self, gradient: etree.Element):
        # Gradients can have an 'href' attribute that specifies another gradient as
        # a template, inheriting its attributes and/or stops when not already defined:
        # https://www.w3.org/TR/SVG/pservers.html#PaintServerTemplates

        assert _is_gradient(gradient)

        href_attr = _xlink_href_attr_name()
        if href_attr not in gradient.attrib:
            return  # nop

        ref = gradient.attrib[href_attr]
        if not ref.startswith("#"):
            raise ValueError(f"Only use #fragment supported, reject {ref}")
        ref = ref[1:].strip()

        template = self.xpath_one(f'.//svg:*[@id="{ref}"]')

        template_tag = strip_ns(template.tag)
        if template_tag not in _GRADIENT_CLASSES:
            raise ValueError(
                f"Referenced element with id='{ref}' has unexpected tag: "
                f"expected linear or radialGradient, found '{template_tag}'"
            )

        # recurse if template references another template
        if template.attrib.get(href_attr):
            self._apply_gradient_template(template)

        for attr_name in _GRADIENT_FIELDS[strip_ns(gradient.tag)]:
            if attr_name in template.attrib and attr_name not in gradient.attrib:
                gradient.attrib[attr_name] = template.attrib[attr_name]

        # only copy stops if we don't have our own
        if len(gradient) == 0:
            for stop_el in template:
                new_stop_el = copy.deepcopy(stop_el)
                # strip stop id if present; useless and no longer unique
                _del_attrs(new_stop_el, "id")
                gradient.append(new_stop_el)

        del gradient.attrib[href_attr]

    def _remove_orphaned_gradients(self):
        # remove orphaned templates, only keep gradients directly referenced by shapes
        used_gradient_ids = set()
        for shape in self.shapes():
            if shape.fill.startswith("url("):
                try:
                    el = self.resolve_url(shape.fill, "*")
                except ValueError:  # skip not found
                    continue
                if strip_ns(el.tag) not in _GRADIENT_CLASSES:
                    # unlikely the url target isn't a gradient but I'm not the police
                    continue
                used_gradient_ids.add(el.attrib["id"])
        for grad in self._select_gradients():
            if grad.attrib.get("id") not in used_gradient_ids:
                _safe_remove(grad)

    def checkpicosvg(self):
        """Check for nano violations, return xpaths to bad elements.

        If result sequence empty then this is a valid picosvg.
        """

        self._update_etree()

        errors = []
        bad_paths = set()

        path_allowlist = {
            r"^/svg\[0\]$",
            r"^/svg\[0\]/defs\[0\]$",
            r"^/svg\[0\]/defs\[0\]/(linear|radial)Gradient\[\d+\](/stop\[\d+\])?$",
            r"^/svg\[0\](/(path|g)\[\d+\])+$",
        }
        paths_required = {
            "/svg[0]",
            "/svg[0]/defs[0]",
        }

        # Make a list of xpaths with offsets (/svg/defs[0]/..., etc)
        ids = {}
        for context in self.breadth_first():
            if any(context.path.startswith(bp) for bp in bad_paths):
                continue  # no sense reporting all the children as bad

            if not any((re.match(pat, context.path) for pat in path_allowlist)):
                errors.append(f"BadElement: {context.path}")
                bad_paths.add(context.path)
                continue

            paths_required.discard(context.path)

            el_id = context.element.attrib.get("id", None)
            if el_id is not None:
                if el_id in ids:
                    errors.append(
                        f'BadElement: {context.path} reuses id="{el_id}", first seen at {ids[el_id]}'
                    )
                ids[el_id] = context.path

        for path in paths_required:
            errors.append(f"MissingElement: {path}")

        # TODO paths, groups, & gradients should only have specific attributes

        return tuple(errors)

    def topicosvg(self, *, ndigits=3, inplace=False):
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.topicosvg(inplace=True)
            return svg

        self._update_etree()

        # Discard useless content
        self.remove_nonsvg_content(inplace=True)
        self.remove_comments(inplace=True)
        self.remove_anonymous_symbols(inplace=True)
        self.remove_title_meta_desc(inplace=True)

        # Simplify things that simplify in isolation
        self.apply_style_attributes(inplace=True)
        self.resolve_nested_svgs(inplace=True)
        self.shapes_to_paths(inplace=True)
        self.expand_shorthand(inplace=True)
        self.resolve_use(inplace=True)

        # Simplify things that do not simplify in isolation
        self.simplify(inplace=True)

        # Tidy up
        self.evenodd_to_nonzero_winding(inplace=True)
        self.remove_unpainted_shapes(inplace=True)
        self.normalize_opacity(inplace=True)
        self.absolute(inplace=True)
        self.round_floats(ndigits, inplace=True)

        nano_violations = self.checkpicosvg()
        if nano_violations:
            raise ValueError(
                "Unable to convert to picosvg: " + ",".join(nano_violations)
            )

        return self

    @staticmethod
    def _swap_elements(swaps: Iterable[Tuple[etree.Element, Sequence[etree.Element]]]):
        for old_el, new_els in swaps:
            for new_el in reversed(new_els):
                old_el.addnext(new_el)
            parent = old_el.getparent()
            if parent is None:
                raise ValueError("Lost parent!")
            parent.remove(old_el)

    def _update_etree(self):
        if not self.elements:
            return
        self._swap_elements(
            (old_el, [to_element(s) for s in shapes])
            for old_el, shapes in self.elements
        )
        self.elements = None

    def toetree(self):
        self._update_etree()
        self.svg_root = _fix_xlink_ns(self.svg_root)
        return copy.deepcopy(self.svg_root)

    def tostring(self, pretty_print=False):
        return etree.tostring(self.toetree(), pretty_print=pretty_print).decode("utf-8")

    @classmethod
    def fromstring(cls, string):
        if isinstance(string, bytes):
            string = string.decode("utf-8")

        # svgs are fond of not declaring xlink
        # based on https://mailman-mail5.webfaction.com/pipermail/lxml/20100323/021184.html
        if "xlink" in string and "xmlns:xlink" not in string:
            string = string.replace("xlink:href", _XLINK_TEMP)

        # encode because fromstring dislikes xml encoding decl if input is str
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.fromstring(string.encode("utf-8"), parser)
        tree = _fix_xlink_ns(tree)
        return cls(tree)

    @classmethod
    def parse(cls, file_or_path):
        if hasattr(file_or_path, "read"):
            raw_svg = file_or_path.read()
        else:
            with open(file_or_path) as f:
                raw_svg = f.read()
        return cls.fromstring(raw_svg)


def _inherit_copy(attrib, child, attr_name):
    if attr_name in child.attrib:
        return
    if attr_name in attrib:
        child.attrib[attr_name] = attrib[attr_name]


def _inherit_multiply(attrib, child, attr_name):
    if attr_name not in attrib and attr_name not in child.attrib:
        return
    value = float(attrib.get(attr_name, 1.0))
    value *= float(child.attrib.get(attr_name, 1.0))
    child.attrib[attr_name] = ntos(value)


def _inherit_clip_path(attrib, child, attr_name):
    clips = sorted(
        child.attrib.get("clip-path", "").split(",") + [attrib.get("clip-path", "")]
    )
    child.attrib["clip-path"] = ",".join([c for c in clips if c])


def _inherit_nondefault_overflow(attrib, child, attr_name):
    value = attrib.get(attr_name, "visible")
    if value != "visible":
        _inherit_copy(attrib, child, attr_name)


def _inherit_matrix_multiply(attrib, child, attr_name):
    transform = Affine2D.identity()
    if attr_name in attrib:
        transform = Affine2D.fromstring(attrib[attr_name])
    if attr_name in child.attrib:
        transform = Affine2D.compose_ltr(
            (Affine2D.fromstring(child.attrib[attr_name]), transform)
        )
    if transform != Affine2D.identity():
        child.attrib[attr_name] = transform.tostring()
    else:
        del child.attrib[attr_name]


def _do_not_inherit(*_):
    return


_INHERIT_ATTRIB_HANDLERS = {
    "clip-rule": _inherit_copy,
    "color": _inherit_copy,
    "display": _inherit_copy,
    "fill": _inherit_copy,
    "fill-rule": _inherit_copy,
    "style": _inherit_copy,
    "transform": _inherit_matrix_multiply,
    "stroke": _inherit_copy,
    "stroke-width": _inherit_copy,
    "stroke-linecap": _inherit_copy,
    "stroke-linejoin": _inherit_copy,
    "stroke-miterlimit": _inherit_copy,
    "stroke-dasharray": _inherit_copy,
    "stroke-dashoffset": _inherit_copy,
    "stroke-opacity": _inherit_copy,
    "fill-opacity": _inherit_copy,
    "opacity": _inherit_multiply,
    "clip-path": _inherit_clip_path,
    "id": _do_not_inherit,
    "data-name": _do_not_inherit,
    "enable-background": _do_not_inherit,
    "overflow": _inherit_nondefault_overflow,
}


_INHERITABLE_ATTRIB = frozenset(
    k for k, v in _INHERIT_ATTRIB_HANDLERS.items() if v is not _do_not_inherit
)


def _attr_supported(el: etree.Element, attr_name: str) -> bool:
    tag = strip_ns(el.tag)
    field_name = _field_name(attr_name)
    if tag in _VALID_FIELDS:
        return field_name in _VALID_FIELDS[tag]
    return True  # we don't know


def _drop_default_attrib(attrib: MutableMapping[str, Any]):
    for attr_name in sorted(attrib.keys()):
        value = attrib[attr_name]
        default_value = attrib_default(attr_name, default=None)
        if default_value is None:
            continue
        if isinstance(default_value, float):
            value = float(value)
        if default_value == value:
            del attrib[attr_name]


def _inherit_attrib(
    attrib: Mapping[str, Any],
    child: etree.Element,
    skip_unhandled: bool = False,
    skips=frozenset(),
):
    attrib = copy.deepcopy(attrib)
    _drop_default_attrib(attrib)
    for attr_name in sorted(attrib.keys()):
        if attr_name in skips or not _attr_supported(child, attr_name):
            del attrib[attr_name]
            continue
        if not attr_name in _INHERIT_ATTRIB_HANDLERS:
            continue
        _INHERIT_ATTRIB_HANDLERS[attr_name](attrib, child, attr_name)
        del attrib[attr_name]

    if len(attrib) and not skip_unhandled:
        raise ValueError(f"Unable to process attrib {attrib}")

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

import copy
import dataclasses
from functools import reduce
from lxml import etree  # pytype: disable=import-error
import re
from typing import List, Optional, Tuple
from picosvg.svg_meta import ntos, svgns, xlinkns
from picosvg import svg_pathops
from picosvg.svg_types import *
import numbers

_ELEMENT_CLASSES = {
    "circle": SVGCircle,
    "ellipse": SVGEllipse,
    "line": SVGLine,
    "path": SVGPath,
    "polygon": SVGPolygon,
    "polyline": SVGPolyline,
    "rect": SVGRect,
}
_CLASS_ELEMENTS = {v: f"{{{svgns()}}}{k}" for k, v in _ELEMENT_CLASSES.items()}
_ELEMENT_CLASSES.update({f"{{{svgns()}}}{k}": v for k, v in _ELEMENT_CLASSES.items()})

_XLINK_TEMP = "xlink_"


# How much error, as pct of viewbox max(w,h), is allowed on lossy ops
# For example, for a Noto Emoji with a viewBox 0 0 128 128 permit error of 0.128
_MAX_PCT_ERROR = 0.1

# When you have no viewbox, use this. Absolute value in svg units.
_DEFAULT_DEFAULT_TOLERENCE = 0.1


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


def _attr_name(field_name):
    return field_name.replace("_", "-")


def _field_name(attr_name):
    return attr_name.replace("-", "_")


def from_element(el):
    if el.tag not in _ELEMENT_CLASSES:
        raise ValueError(f"Bad tag <{el.tag}>")
    data_type = _ELEMENT_CLASSES[el.tag]
    args = {
        f.name: f.type(el.attrib[_attr_name(f.name)])
        for f in dataclasses.fields(data_type)
        if _attr_name(f.name) in el.attrib
    }
    return data_type(**args)


def to_element(data_obj):
    el = etree.Element(_CLASS_ELEMENTS[type(data_obj)])
    data = dataclasses.asdict(data_obj)
    for field in dataclasses.fields(data_obj):
        field_value = data[field.name]
        if field_value == field.default:
            continue
        attrib_value = field_value
        if isinstance(attrib_value, numbers.Number):
            attrib_value = ntos(attrib_value)
        el.attrib[_attr_name(field.name)] = attrib_value
    return el


def _reset_attrs(data_obj, field_pred):
    for field in dataclasses.fields(data_obj):
        if field_pred(field):
            setattr(data_obj, field.name, field.default)


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
        for el in self.svg_root.iter("*"):
            if el.tag not in _ELEMENT_CLASSES:
                continue
            elements.append((el, (from_element(el),)))
        self.elements = elements
        return self.elements

    def _set_element(self, idx: int, el: etree.Element, shapes: Tuple[SVGShape, ...]):
        self.elements[idx] = (el, shapes)

    def view_box(self) -> Optional[Rect]:
        raw_box = self.svg_root.attrib.get("viewBox", None)
        if not raw_box:
            return None
        box = tuple(int(v) for v in re.split(r",|\s+", raw_box))
        if len(box) != 4:
            raise ValueError("Unable to parse viewBox")
        return Rect(*box)

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

    def xpath(self, xpath, el=None):
        if el is None:
            el = self.svg_root
        return el.xpath(xpath, namespaces={"svg": svgns()})

    def xpath_one(self, xpath):
        els = self.xpath(xpath)
        if len(els) != 1:
            raise ValueError(f"Need exactly 1 match for {xpath}, got {len(els)}")
        return els[0]

    def resolve_url(self, url, el_tag):
        match = re.match(r"^url[(]#([\w-]+)[)]$", url)
        if not match:
            raise ValueError(f'Unrecognized url "{url}"')
        return self.xpath_one(f'//svg:{el_tag}[@id="{match.group(1)}"]')

    def _resolve_use(self, scope_el):
        attrib_not_copied = {"x", "y", "width", "height", _xlink_href_attr_name()}

        swaps = []

        for use_el in self.xpath(".//svg:use", el=scope_el):
            ref = use_el.attrib.get(_xlink_href_attr_name(), "")
            if not ref.startswith("#"):
                raise ValueError("Only use #fragment supported")
            target = self.xpath_one(f'//svg:*[@id="{ref[1:]}"]')

            new_el = copy.deepcopy(target)

            group = etree.Element(f"{{{svgns()}}}g", nsmap=self.svg_root.nsmap)
            use_x = use_el.attrib.get("x", 0)
            use_y = use_el.attrib.get("y", 0)
            if use_x != 0 or use_y != 0:
                group.attrib["transform"] = (
                    group.attrib.get("transform", "") + f" translate({use_x}, {use_y})"
                ).strip()

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
        clip_path_el = self.resolve_url(clip_path_url, "clipPath")
        self._resolve_use(clip_path_el)
        self._ungroup(clip_path_el)

        # union all the shapes under the clipPath
        # Fails if there are any non-shapes under clipPath
        clip_path = SVGPath.from_commands(
            svg_pathops.union(*[from_element(e).as_cmd_seq() for e in clip_path_el])
        )
        return clip_path

    def append_to(self, xpath, el):
        self._update_etree()
        self.xpath_one(xpath).append(el)
        return el

    def _combine_clip_paths(self, clip_paths) -> SVGPath:
        # multiple clip paths leave behind their intersection
        if not clip_paths:
            raise ValueError("Cannot combine no clip_paths")
        if len(clip_paths) == 1:
            return clip_paths[0]
        return SVGPath.from_commands(
            svg_pathops.intersection(*[c.as_cmd_seq() for c in clip_paths])
        )

    def _new_id(self, tag, template):
        for i in range(100):
            potential_id = template % i
            existing = self.xpath(f'//svg:{tag}[@id="{potential_id}"]')
            if not existing:
                return potential_id
        raise ValueError(f"No free id for {template}")

    def _inherit_group_attrib(self, group, child):
        def _inherit_copy(attrib, child, attr_name):
            child.attrib[attr_name] = child.attrib.get(attr_name, attrib[attr_name])

        def _inherit_multiply(attrib, child, attr_name):
            value = float(attrib[attr_name])
            value *= float(child.attrib.get(attr_name, 1.0))
            child.attrib[attr_name] = ntos(value)

        def _inherit_clip_path(attrib, child, attr_name):
            clips = sorted(
                child.attrib.get("clip-path", "").split(",") + [attrib.get("clip-path")]
            )
            child.attrib["clip-path"] = ",".join([c for c in clips if c])

        def _inherit_nondefault_overflow(attrib, child, attr_name):
            value = attrib[attr_name]
            if value != "visible":
                _inherit_copy(attrib, child, attr_name)

        attrib_handlers = {
            "fill": _inherit_copy,
            "stroke": _inherit_copy,
            "stroke-width": _inherit_copy,
            "stroke-linecap": _inherit_copy,
            "stroke-linejoin": _inherit_copy,
            "stroke-miterlimit": _inherit_copy,
            "stroke-dasharray": _inherit_copy,
            "fill-opacity": _inherit_multiply,
            "opacity": _inherit_multiply,
            "clip-path": _inherit_clip_path,
            "id": lambda *_: 0,
            "data-name": lambda *_: 0,
            "overflow": _inherit_nondefault_overflow,
        }

        attrib = copy.deepcopy(group.attrib)
        for attr_name in sorted(attrib.keys()):
            if not attr_name in attrib_handlers:
                continue
            attrib_handlers[attr_name](attrib, child, attr_name)
            del attrib[attr_name]

        if attrib:
            raise ValueError(f"Unable to process group attrib {attrib}")

    def _ungroup(self, scope_el):
        """Push inherited attributes from group down, then remove the group.

        Drop groups that are not displayed.

        If result has multiple clip paths merge them.
        """
        # nuke the groups that are not displayed
        display_none = [e for e in self.xpath(f".//svg:g[@display='none']", scope_el)]
        for group in display_none:
            if group.getparent() is not None:
                group.getparent().remove(group)

        # Any groups left are displayed
        groups = [e for e in self.xpath(f".//svg:g", scope_el)]
        multi_clips = []
        for group in groups:
            # move groups children up
            # reverse because "for each addnext" effectively reverses
            children = list(group)
            children.reverse()
            for child in children:
                group.remove(child)
                group.addnext(child)

                self._inherit_group_attrib(group, child)
                if "," in child.attrib.get("clip-path", ""):
                    multi_clips.append(child)

        # nuke the groups
        for group in groups:
            if group.getparent() is not None:
                group.getparent().remove(group)

        # if we have new combinations of clip paths dedup & materialize them
        new_clip_paths = {}
        old_clip_paths = []
        for clipped_el in multi_clips:
            clip_refs = clipped_el.attrib["clip-path"]
            clip_ref_urls = clip_refs.split(",")
            old_clip_paths.extend(
                [self.resolve_url(ref, "clipPath") for ref in clip_ref_urls]
            )
            clip_paths = [self._resolve_clip_path(ref) for ref in clip_ref_urls]
            clip_path = self._combine_clip_paths(clip_paths)
            if clip_path.d not in new_clip_paths:
                new_el = etree.SubElement(self.svg_root, "clipPath")
                new_el.attrib["id"] = self._new_id("clipPath", "merged-clip-%d")
                new_el.append(to_element(clip_path))
                new_clip_paths[clip_path.d] = new_el

            new_ref_id = new_clip_paths[clip_path.d].attrib["id"]
            clipped_el.attrib["clip-path"] = f"url(#{new_ref_id})"

        # destroy unreferenced clip paths
        for old_clip_path in old_clip_paths:
            if old_clip_path.getparent() is None:
                continue
            old_id = old_clip_path.attrib["id"]
            if not self.xpath(f'//svg:*[@clip-path="url(#{old_id})"]'):
                old_clip_path.getparent().remove(old_clip_path)

    def _compute_clip_path(self, el):
        """Resolve clip path for element, including inherited clipping.

        None if there is no clipping.

        https://www.w3.org/TR/SVG11/masking.html#EstablishingANewClippingPath
        """
        clip_paths = []
        while el is not None:
            clip_url = el.attrib.get("clip-path", None)
            if clip_url:
                clip_paths.append(self._resolve_clip_path(clip_url))
            el = el.getparent()

        if not clip_paths:
            return None
        return self._combine_clip_paths(clip_paths)

    def ungroup(self, inplace=False):
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.ungroup(inplace=True)
            return svg

        self._update_etree()
        self._ungroup(self.svg_root)
        return self

    def _stroke(self, shape):
        """Convert stroke to path.

        Returns sequence of shapes in draw order. That is, result[1] should be
        drawn on top of result[0], etc."""

        def stroke_pred(field):
            return field.name.startswith("stroke")

        # map old fields to new dest
        _stroke_fields = {"stroke": "fill", "stroke_opacity": "opacity"}

        if shape.stroke == "none":
            return (shape,)

        # make a new path that is the stroke
        stroke = SVGPath.from_commands(
            svg_pathops.stroke(
                shape.as_cmd_seq(),
                shape.stroke_linecap,
                shape.stroke_linejoin,
                shape.stroke_width,
                shape.stroke_miterlimit,
                self.tolerance,
            )
        )

        # convert some stroke attrs (e.g. stroke => fill)
        for field in dataclasses.fields(shape):
            dest_field = _stroke_fields.get(field.name, None)
            if not dest_field:
                continue
            setattr(stroke, dest_field, getattr(shape, field.name))

        # remove all the stroke settings
        _reset_attrs(shape, stroke_pred)

        if shape.fill == "none":
            return (stroke,)

        return (shape, stroke)

    def strokes_to_paths(self, inplace=False):
        """Convert stroked shapes to equivalent filled shape + path for stroke."""
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.strokes_to_paths(inplace=True)
            return svg

        self._update_etree()

        # Find stroked things
        stroked = []
        for idx, (el, (shape,)) in enumerate(self._elements()):
            if shape.stroke == "none":
                continue
            stroked.append(idx)

        # Stroke 'em
        for idx in stroked:
            el, shapes = self.elements[idx]
            shapes = sum((self._stroke(s) for s in shapes), ())
            self._set_element(idx, el, shapes)

        # Update the etree
        self._update_etree()

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
            el, (target,) = self.elements[el_idx]
            target = target.as_path().absolute(inplace=True)

            target.d = SVGPath.from_commands(
                svg_pathops.intersection(target.as_cmd_seq(), clip_path.as_cmd_seq())
            ).d
            target.clip_path = ""
            self._set_element(el_idx, el, (target,))

        # destroy clip path elements
        for clip_path_el in self.xpath("//svg:clipPath"):
            clip_path_el.getparent().remove(clip_path_el)

        # destroy clip-path attributes
        self.remove_attributes(["clip-path"], xpath="//svg:*[@clip-path]", inplace=True)

        return self

    def apply_transforms(self, inplace=False):
        """Naively transforms to shapes and removes the transform attribute.

        Naive: just applies any transform on a parent element.
        """
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.apply_transforms(inplace=True)
            return svg

        self._update_etree()

        # figure out the sequence of transforms, if any, for each shape
        new_shapes = []
        for idx, (el, (shape,)) in enumerate(self._elements()):
            transform = Affine2D.identity()
            while el is not None:
                if "transform" in el.attrib:
                    transform = Affine2D.product(
                        transform, Affine2D.fromstring(el.attrib["transform"])
                    )
                el = el.getparent()
            if transform != Affine2D.identity():
                new_shapes.append((idx, shape.apply_transform(transform)))

        for el_idx, new_shape in new_shapes:
            el, _ = self.elements[el_idx]
            self._set_element(el_idx, el, (new_shape,))

        # destroy all transform attributes
        self.remove_attributes(["transform"], xpath="//svg:*[@transform]", inplace=True)

        return self

    def remove_unpainted_shapes(self, inplace=False):
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.remove_unpainted_shapes(inplace=True)
            return svg

        self._update_etree()

        remove = []
        for (el, (shape,)) in self._elements():
            if not shape.visible():
                remove.append(el)

        for el in remove:
            el.getparent().remove(el)

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

    def checkpicosvg(self):
        """Check for nano violations, return xpaths to bad elements.

        If result sequence empty then this is a valid picosvg.
        """

        def _strip_ns(tagname):
            if "}" in tagname:
                return tagname[tagname.index("}") + 1 :]
            return tagname

        self._update_etree()

        errors = []

        path_whitelist = {
            r"^/svg\[0\]$",
            r"^/svg\[0\]/defs\[0\]$",
            r"^/svg\[0\]/defs\[0\]/(linear|radial)Gradient\[\d+\](/stop\[\d+\])?$",
            r"^/svg\[0\]/path\[(?!0\])\d+\]$",
        }

        # Make a list of xpaths with offsets (/svg/defs[0]/..., etc)
        frontier = [(0, self.svg_root, "")]
        while frontier:
            el_idx, el, parent_path = frontier.pop(0)
            el_tag = _strip_ns(el.tag)
            el_path = f"{parent_path}/{el_tag}[{el_idx}]"

            if not any((re.match(pat, el_path) for pat in path_whitelist)):
                errors.append(f"BadElement: {el_path}")

            for child_idx, child in enumerate(el):
                if child.tag is etree.Comment:
                    continue
                frontier.append((child_idx, child, el_path))

        # TODO paths & gradients should only have specific attributes

        return tuple(errors)

    def topicosvg(self, inplace=False):
        if not inplace:
            svg = SVG(copy.deepcopy(self.svg_root))
            svg.topicosvg(inplace=True)
            return svg

        self._update_etree()

        self.remove_comments(inplace=True)
        self.shapes_to_paths(inplace=True)
        self.resolve_use(inplace=True)
        self.apply_transforms(inplace=True)
        self.apply_clip_paths(inplace=True)
        self.ungroup(inplace=True)
        # stroke after ungroup to apply group strokes properly
        self.strokes_to_paths(inplace=True)
        self.remove_unpainted_shapes(inplace=True)

        # Collect gradients; remove other defs
        defs = etree.Element(f"{{{svgns()}}}defs", nsmap=self.svg_root.nsmap)
        for gradient in self.xpath("//svg:linearGradient | //svg:radialGradient"):
            gradient.getparent().remove(gradient)
            defs.append(gradient)

        for def_el in [e for e in self.xpath("//svg:defs")]:
            def_el.getparent().remove(def_el)

        self.svg_root.insert(0, defs)

        nano_violations = self.checkpicosvg()
        if nano_violations:
            raise ValueError(
                "Unable to convert to picosvg: " + ",".join(nano_violations)
            )

        return self

    def _update_etree(self):
        if not self.elements:
            return
        swaps = []
        for old_el, shapes in self.elements:
            swaps.append((old_el, [to_element(s) for s in shapes]))
        for old_el, new_els in swaps:
            for new_el in reversed(new_els):
                old_el.addnext(new_el)
            parent = old_el.getparent()
            if parent is None:
                raise ValueError("Lost parent!")
            parent.remove(old_el)
        self.elements = None

    def toetree(self):
        self._update_etree()
        self.svg_root = _fix_xlink_ns(self.svg_root)
        return copy.deepcopy(self.svg_root)

    def tostring(self):
        return etree.tostring(self.toetree()).decode("utf-8")

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

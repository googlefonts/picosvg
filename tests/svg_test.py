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

import dataclasses
from copy import deepcopy
from textwrap import dedent
from lxml import etree
import math
import os
import pytest
from picosvg.svg import SVG, SVGPath
from picosvg.svg_meta import strip_ns, parse_css_declarations
import re
from svg_test_helpers import *
from typing import Tuple


def _test(actual, expected_result, op):
    actual = op(load_test_svg(actual))
    expected_result = load_test_svg(expected_result)
    drop_whitespace(actual)
    drop_whitespace(expected_result)
    print(f"A: {pretty_print(actual.toetree())}")
    print(f"E: {pretty_print(expected_result.toetree())}")
    assert pretty_print(actual.toetree()) == pretty_print(expected_result.toetree())


@pytest.mark.parametrize(
    "shape, expected_fields",
    [
        # path, fill
        ("<path d='M1,1 2,2' fill='blue' />", {"fill": "blue"}),
        # rect, opacity
        ("<rect x='5' y='5' width='5' height='5' opacity='0.5'/>", {"opacity": 0.5}),
        # polyline, clip-path
        (
            "<polyline points='1,1 5,5 2,2' clip-path='url(#cp)'/>",
            {"clip_path": "url(#cp)"},
        ),
        # line, stroke
        ("<line x1='1' y1='1' x2='10' y2='10' stroke='red'/>", {"stroke": "red"}),
    ],
)
def test_common_attrib(shape, expected_fields):
    svg = SVG.fromstring(svg_string(shape))
    field_values = dataclasses.asdict(svg.shapes()[0])
    for field_name, expected_value in expected_fields.items():
        assert field_values.get(field_name, "") == expected_value, field_name

    svg = svg.shapes_to_paths()
    field_values = dataclasses.asdict(svg.shapes()[0])
    for field_name, expected_value in expected_fields.items():
        assert field_values.get(field_name, "") == expected_value, field_name


# https://www.w3.org/TR/SVG11/shapes.html
@pytest.mark.parametrize(
    "shape, expected_path",
    [
        # path: direct passthrough
        ("<path d='I love kittens'/>", 'd="I love kittens"'),
        # path no @d
        ("<path duck='Mallard'/>", ""),
        # line
        ('<line x1="10" x2="50" y1="110" y2="150"/>', 'd="M10,110 L50,150"'),
        # line, decimal positioning
        (
            '<line x1="10.0" x2="50.5" y1="110.2" y2="150.7"/>',
            'd="M10,110.2 L50.5,150.7"',
        ),
        # rect: minimal valid example
        ("<rect width='1' height='1'/>", 'd="M0,0 H1 V1 H0 V0 Z"'),
        # rect: sharp corners
        (
            "<rect x='10' y='11' width='17' height='11'/>",
            'd="M10,11 H27 V22 H10 V11 Z"',
        ),
        # rect: round corners
        (
            "<rect x='9' y='9' width='11' height='7' rx='2'/>",
            'd="M11,9 H18 A2 2 0 0 1 20,11 V14 A2 2 0 0 1 18,16 H11'
            ' A2 2 0 0 1 9,14 V11 A2 2 0 0 1 11,9 Z"',
        ),
        # rect: simple
        (
            "<rect x='11.5' y='16' width='11' height='2'/>",
            'd="M11.5,16 H22.5 V18 H11.5 V16 Z"',
        ),
        # polygon
        ("<polygon points='30,10 50,30 10,30'/>", 'd="M30,10 50,30 10,30 Z"'),
        # polyline
        ("<polyline points='30,10 50,30 10,30'/>", 'd="M30,10 50,30 10,30"'),
        # circle, minimal valid example
        ("<circle r='1'/>", 'd="M1,0 A1 1 0 1 1 -1,0 A1 1 0 1 1 1,0 Z"'),
        # circle
        (
            "<circle cx='600' cy='200' r='100'/>",
            'd="M700,200 A100 100 0 1 1 500,200 A100 100 0 1 1 700,200 Z"',
        ),
        # circle, decimal positioning
        (
            "<circle cx='12' cy='6.5' r='1.5'></circle>",
            'd="M13.5,6.5 A1.5 1.5 0 1 1 10.5,6.5 A1.5 1.5 0 1 1 13.5,6.5 Z"',
        ),
        # ellipse
        (
            '<ellipse cx="100" cy="50" rx="100" ry="50"/>',
            'd="M200,50 A100 50 0 1 1 0,50 A100 50 0 1 1 200,50 Z"',
        ),
        # ellipse, decimal positioning
        (
            '<ellipse cx="100.5" cy="50" rx="10" ry="50.5"/>',
            'd="M110.5,50 A10 50.5 0 1 1 90.5,50 A10 50.5 0 1 1 110.5,50 Z"',
        ),
    ],
)
def test_shapes_to_paths(shape: str, expected_path: str):
    actual = SVG.fromstring(svg_string(shape)).shapes_to_paths(inplace=True).toetree()
    expected_result = SVG.fromstring(svg_string(f"<path {expected_path}/>")).toetree()
    print(f"A: {pretty_print(actual)}")
    print(f"E: {pretty_print(expected_result)}")
    assert etree.tostring(actual) == etree.tostring(expected_result)


@pytest.mark.parametrize(
    "shape, expected_cmds",
    [
        # line
        (
            '<line x1="10" x2="50" y1="110" y2="150"/>',
            [("M", (10.0, 110.0)), ("L", (50.0, 150.0))],
        ),
        # path explodes to show implicit commands
        (
            '<path d="m1,1 2,0 1,3"/>',
            [("m", (1.0, 1.0)), ("l", (2.0, 0.0)), ("l", (1.0, 3.0))],
        ),
        # vertical and horizontal movement
        (
            '<path d="m1,1 v2 h2z"/>',
            [("m", (1.0, 1.0)), ("v", (2.0,)), ("h", (2.0,)), ("z", ())],
        ),
        # arc, negative offsets
        (
            '<path d="M7,5 a3,1 0,0,0 0,-3 a3,3 0 0 1 -4,2"/>',
            [
                ("M", (7.0, 5.0)),
                ("a", (3.0, 1.0, 0.0, 0.0, 0.0, 0.0, -3.0)),
                ("a", (3.0, 3.0, 0.0, 0.0, 1.0, -4.0, 2.0)),
            ],
        ),
        # minimalist numbers, who needs spaces or commas
        (
            '<path d="m-1-1 0.5-.5-.5-.3.1.2.2.51.52.711"/>',
            [
                ("m", (-1.0, -1.0)),
                ("l", (0.5, -0.5)),
                ("l", (-0.5, -0.3)),
                ("l", (0.1, 0.2)),
                ("l", (0.2, 0.51)),
                ("l", (0.52, 0.711)),
            ],
        ),
    ],
)
def test_iter(shape, expected_cmds):
    svg_path = SVG.fromstring(svg_string(shape)).shapes_to_paths().shapes()[0]
    actual_cmds = [t for t in svg_path]
    print(f"A: {actual_cmds}")
    print(f"E: {expected_cmds}")
    assert actual_cmds == expected_cmds


@pytest.mark.parametrize(
    "actual, expected_result", [("use-ellipse.svg", "use-ellipse-resolved.svg")]
)
def test_resolve_use(actual, expected_result):
    _test(actual, expected_result, lambda svg: svg.resolve_use(inplace=True))


@pytest.mark.parametrize(
    "actual, expected_result",
    [
        ("stroke-simplepath-before.svg", "stroke-simplepath-nano.svg"),
        ("stroke-path-before.svg", "stroke-path-nano.svg"),
        ("stroke-capjoinmiterlimit-before.svg", "stroke-capjoinmiterlimit-nano.svg"),
        ("scale-strokes-before.svg", "scale-strokes-nano.svg"),
        ("stroke-fill-opacity-before.svg", "stroke-fill-opacity-nano.svg"),
        ("stroke-dasharray-before.svg", "stroke-dasharray-nano.svg"),
        ("stroke-circle-dasharray-before.svg", "stroke-circle-dasharray-nano.svg"),
        ("clip-rect.svg", "clip-rect-clipped-nano.svg"),
        ("clip-ellipse.svg", "clip-ellipse-clipped-nano.svg"),
        ("clip-curves.svg", "clip-curves-clipped-nano.svg"),
        ("clip-multirect.svg", "clip-multirect-clipped-nano.svg"),
        ("clip-groups.svg", "clip-groups-clipped-nano.svg"),
        ("clip-use.svg", "clip-use-clipped-nano.svg"),
        ("clip-rule-example.svg", "clip-rule-example-nano.svg"),
        ("clip-from-brazil-flag.svg", "clip-from-brazil-flag-nano.svg"),
        ("clip-rule-evenodd.svg", "clip-rule-evenodd-clipped-nano.svg"),
        ("clip-clippath-attrs.svg", "clip-clippath-attrs-nano.svg"),
        ("clip-clippath-none.svg", "clip-clippath-none-nano.svg"),
        ("rotated-rect.svg", "rotated-rect-nano.svg"),
        ("translate-rect.svg", "translate-rect-nano.svg"),
        ("ungroup-before.svg", "ungroup-nano.svg"),
        ("ungroup-multiple-children-before.svg", "ungroup-multiple-children-nano.svg"),
        ("group-stroke-before.svg", "group-stroke-nano.svg"),
        ("arcs-before.svg", "arcs-nano.svg"),
        ("invisible-before.svg", "invisible-nano.svg"),
        ("transform-before.svg", "transform-nano.svg"),
        ("group-data-name-before.svg", "group-data-name-nano.svg"),
        ("matrix-before.svg", "matrix-nano.svg"),
        ("degenerate-before.svg", "degenerate-nano.svg"),
        ("fill-rule-evenodd-before.svg", "fill-rule-evenodd-nano.svg"),
        ("twemoji-lesotho-flag-before.svg", "twemoji-lesotho-flag-nano.svg"),
        ("inline-css-style-before.svg", "inline-css-style-nano.svg"),
        ("clipped-strokes-before.svg", "clipped-strokes-nano.svg"),
        ("drop-anon-symbols-before.svg", "drop-anon-symbols-nano.svg"),
        ("scale-strokes-before.svg", "scale-strokes-nano.svg"),
        ("ungroup-with-ids-before.svg", "ungroup-with-ids-nano.svg"),
        ("stroke-with-id-before.svg", "stroke-with-id-nano.svg"),
        ("drop-title-meta-desc-before.svg", "drop-title-meta-desc-nano.svg"),
        ("no-viewbox-before.svg", "no-viewbox-nano.svg"),
        ("decimal-viewbox-before.svg", "decimal-viewbox-nano.svg"),
        ("inkscape-noise-before.svg", "inkscape-noise-nano.svg"),
        ("flag-use-before.svg", "flag-use-nano.svg"),
        ("ungroup-transform-before.svg", "ungroup-transform-nano.svg"),
        ("pathops-tricky-path-before.svg", "pathops-tricky-path-nano.svg"),
        ("gradient-template-1-before.svg", "gradient-template-1-nano.svg"),
        ("nested-svg-slovenian-flag-before.svg", "nested-svg-slovenian-flag-nano.svg"),
        ("global-fill-none-before.svg", "global-fill-none-nano.svg"),
        ("stroke-polyline-before.svg", "stroke-polyline-nano.svg"),
        ("clip-the-clip-before.svg", "clip-the-clip-nano.svg"),
        ("ungroup-group-transform-before.svg", "ungroup-group-transform-nano.svg"),
        ("ungroup-transform-clip-before.svg", "ungroup-transform-clip-nano.svg"),
        (
            "ungroup-retain-for-opacity-before.svg",
            "ungroup-retain-for-opacity-nano.svg",
        ),
        (
            "transform-radial-userspaceonuse-before.svg",
            "transform-radial-userspaceonuse-nano.svg",
        ),
        (
            "transform-linear-objectbbox-before.svg",
            "transform-linear-objectbbox-nano.svg",
        ),
        (
            "transform-radial-objectbbox-before.svg",
            "transform-radial-objectbbox-nano.svg",
        ),
        (
            "illegal-inheritance-before.svg",
            "illegal-inheritance-nano.svg",
        ),
        (
            "explicit-default-fill-no-inherit-before.svg",
            "explicit-default-fill-no-inherit-nano.svg",
        ),
        (
            "explicit-default-stroke-no-inherit-before.svg",
            "explicit-default-stroke-no-inherit-nano.svg",
        ),
        (
            "inherit-default-fill-before.svg",
            "inherit-default-fill-nano.svg",
        ),
        # propagation of display:none
        (
            "display_none-before.svg",
            "display_none-nano.svg",
        ),
        # https://github.com/googlefonts/picosvg/issues/252
        (
            "strip_empty_subpath-before.svg",
            "strip_empty_subpath-nano.svg",
        ),
        (
            "xpacket-before.svg",
            "xpacket-nano.svg",
        ),
        # https://github.com/googlefonts/picosvg/issues/297
        # Demonstrate comments outside root drop just fine
        (
            "comments-before.svg",
            "comments-nano.svg",
        ),
    ],
)
def test_topicosvg(actual, expected_result):
    _test(actual, expected_result, lambda svg: svg.topicosvg())


@pytest.mark.parametrize("inplace", [True, False])
@pytest.mark.parametrize(
    "actual, expected_result",
    [
        # https://github.com/googlefonts/picosvg/issues/297
        (
            "comments-image-style-before.svg",
            "comments-image-style-nano.svg",
        ),
    ],
)
def test_topicosvg_drop_unsupported(actual, inplace, expected_result):
    actual_copy = deepcopy(actual)
    # This should fail unless we drop unsupported
    with pytest.raises(ValueError) as e:
        _test(actual_copy, expected_result, lambda svg: svg.topicosvg(inplace=inplace))
    assert "BadElement" in str(e.value)
    actual_copy = deepcopy(actual)
    _test(
        actual_copy,
        expected_result,
        lambda svg: svg.topicosvg(inplace=inplace, drop_unsupported=True),
    )


@pytest.mark.parametrize(
    "actual, expected_result",
    [
        ("outside-viewbox.svg", "outside-viewbox-clipped.svg"),
        ("outside-viewbox-grouped.svg", "outside-viewbox-grouped-clipped.svg"),
    ],
)
def test_clip_to_viewbox(actual, expected_result):
    _test(actual, expected_result, lambda svg: svg.clip_to_viewbox().round_floats(4))


@pytest.mark.parametrize(
    "actual, expected_result", [("invisible-before.svg", "invisible-after.svg")]
)
def test_remove_unpainted_shapes(actual, expected_result):
    _test(actual, expected_result, lambda svg: svg.remove_unpainted_shapes())


@pytest.mark.parametrize(
    "svg_file, expected_violations",
    [
        ("good-defs-0.svg", ()),
        (
            "bad-defs-0.svg",
            (
                "BadElement: /svg[0]/defs[1]",
                "BadElement: /svg[0]/donkey[0]",
            ),
        ),
        ("bad-defs-1.svg", ("MissingElement: /svg[0]/defs[0]",)),
        (
            "bad-ids-1.svg",
            (
                'BadElement: /svg[0]/path[1] reuses id="not_so_unique", first seen at /svg[0]/path[0]',
            ),
        ),
    ],
)
def test_checkpicosvg(svg_file, expected_violations):
    nano_violations = load_test_svg(svg_file).checkpicosvg()
    assert expected_violations == nano_violations


@pytest.mark.parametrize(
    "svg_string, expected_result",
    [
        ('<svg version="1.1" xmlns="http://www.w3.org/2000/svg"/>', None),
        (
            '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="" height=""/>',
            None,
        ),
        (
            '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="7 7 12 12"/>',
            (7, 7, 12, 12),
        ),
        (
            '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="6" height="7"/>',
            (0, 0, 6, 7),
        ),
        (
            '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="6px" height="7px"/>',
            (0, 0, 6, 7),
        ),
    ],
)
def test_viewbox(svg_string, expected_result):
    assert SVG.fromstring(svg_string).view_box() == expected_result


@pytest.mark.parametrize(
    "svg_string",
    [
        '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="-6" height="-7"/>',
        '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="0" height="10"/>',
        '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="6pt" height="7pt"/>',
    ],
)
def test_viewbox_valueerror(svg_string):
    with pytest.raises(ValueError):
        SVG.fromstring(svg_string).view_box()


@pytest.mark.parametrize(
    "svg_string, names, expected_result",
    [
        # No change
        (
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.1"/>',
            ("viewBox", "width", "height"),
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.1"/>',
        ),
        # Drop viewBox, width, height
        (
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="7 7 12 12" height="7" width="11"/>',
            ("viewBox", "width", "height"),
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.1"/>',
        ),
        # Drop width, height
        (
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="7 7 12 12" height="7" width="11"/>',
            ("width", "height"),
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="7 7 12 12"/>',
        ),
    ],
)
def test_remove_attributes(svg_string, names, expected_result):
    assert (
        SVG.fromstring(svg_string).remove_attributes(names).tostring()
    ) == expected_result


# https://github.com/rsheeter/picosvg/issues/1
@pytest.mark.parametrize(
    "svg_string, expected_result",
    [
        (
            '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="7 7 12 12"/>',
            0.012,
        ),
        (
            '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"/>',
            0.128,
        ),
    ],
)
def test_tolerance(svg_string, expected_result):
    assert round(SVG.fromstring(svg_string).tolerance, 4) == expected_result


@pytest.mark.parametrize(
    "style, property_names, expected_output, expected_unparsed",
    [
        ("fill:none", None, {"fill": "none"}, ""),
        ("fill: url(#grad1)", None, {"fill": "url(#grad1)"}, ""),
        (
            " stroke  : blue   ; stroke-width :4;   ",
            None,
            {"stroke": "blue", "stroke-width": "4"},
            "",
        ),
        (
            "enable-background:new 0 0 128 128; foo:abc; bar:123;",
            {"enable-background"},
            {"enable-background": "new 0 0 128 128"},
            "foo:abc; bar:123;",
        ),
        (
            # does not support vendor style attributes due to lxml module, see #293
            "stroke:#FF0000;stroke-width:0.5;fill:none;-inkscape-font-specification:'Roboto';",
            None,
            {"stroke": "#FF0000", "stroke-width": "0.5", "fill": "none"},
            "-inkscape-font-specification:'Roboto';",
        ),
    ],
)
def test_parse_css_declarations(
    style, property_names, expected_output, expected_unparsed
):
    element = etree.Element("test")
    output = element.attrib
    unparsed = parse_css_declarations(style, output, property_names)
    assert output == expected_output
    assert unparsed == expected_unparsed


@pytest.mark.parametrize("style", ["foo;bar;", "foo:bar:baz;"])
def test_parse_css_declarations_invalid(style):
    with pytest.raises(ValueError, match="Invalid CSS declaration syntax"):
        parse_css_declarations(style, {})


@pytest.mark.parametrize(
    "actual, expected_result",
    [("inline-css-style-before.svg", "inline-css-style-after.svg")],
)
def test_apply_style_attributes(actual, expected_result):
    _test(actual, expected_result, lambda svg: svg.apply_style_attributes())
    # check we get the same output even if shapes were already parsed
    _test(
        actual,
        expected_result,
        lambda svg: svg.shapes() and svg.apply_style_attributes(),
    )


@pytest.mark.parametrize(
    "gradient_string, expected_result",
    [
        # No transform, no change
        (
            '<linearGradient id="c" x1="63.85" x2="63.85" y1="4245" y2="4137.3" gradientUnits="userSpaceOnUse"/>',
            '<linearGradient id="c" x1="63.85" y1="4245" x2="63.85" y2="4137.3" gradientUnits="userSpaceOnUse"/>',
        ),
        # Real example from emoji_u1f392.svg w/ dx changed from 0 to 1
        # scale, translate
        (
            '<linearGradient id="c" x1="63.85" x2="63.85" y1="4245" y2="4137.3" gradientTransform="translate(1 -4122)" gradientUnits="userSpaceOnUse"/>',
            '<linearGradient id="c" x1="64.85" y1="123" x2="64.85" y2="15.3" gradientUnits="userSpaceOnUse"/>',
        ),
        # Real example from emoji_u1f392.svg w/sx changed from 1 to 0.5
        # scale, translate
        (
            '<radialGradient id="b" cx="63.523" cy="12368" r="53.477" gradientTransform="matrix(.5 0 0 .2631 0 -3150)" gradientUnits="userSpaceOnUse"/>',
            '<radialGradient id="b" cx="63.523" cy="395.366021" r="53.477" gradientTransform="matrix(0.5 0 0 0.2631 0 0)" gradientUnits="userSpaceOnUse"/>',
        ),
        # Real example from emoji_u1f44d.svg
        # Using all 6 parts
        (
            '<radialGradient id="d" cx="2459.4" cy="-319.18" r="20.331" gradientTransform="matrix(-1.3883 .0794 -.0374 -.6794 3505.4 -353.39)" gradientUnits="userSpaceOnUse"/>',
            '<radialGradient id="d" cx="-71.60264" cy="-94.82264" r="20.331" gradientTransform="matrix(-1.3883 0.0794 -0.0374 -0.6794 0 0)" gradientUnits="userSpaceOnUse"/>',
        ),
        # Manually constructed objectBBox
        (
            '<radialGradient id="mbbox" cx="0.75" cy="0.75" r="0.40" gradientTransform="matrix(1 1 -0.7873 -0.001717 0.5 0)" gradientUnits="objectBoundingBox"/>',
            '<radialGradient id="mbbox" cx="0.748907" cy="0.11353" r="0.4" gradientTransform="matrix(1 1 -0.7873 -0.001717 0 0)"/>',
        ),
        # Real example from emoji_u26BE
        # https://github.com/googlefonts/picosvg/issues/129
        (
            '<radialGradient id="f" cx="-779.79" cy="3150" r="58.471" gradientTransform="matrix(0 1 -1 0 3082.5 1129.5)" gradientUnits="userSpaceOnUse"/>',
            '<radialGradient id="f" cx="349.71" cy="67.5" r="58.471" gradientTransform="matrix(0 1 -1 0 0 0)" gradientUnits="userSpaceOnUse"/>',
        ),
        # Real example from emoji_u270c.svg
        # Very small values (e-17...) and float math makes for large errors
        (
            '<radialGradient id="f" cx="75.915" cy="20.049" r="71.484" fx="88.617" fy="-50.297" gradientTransform="matrix(6.1232e-17 1 -1.0519 6.4408e-17 97.004 -55.866)" gradientUnits="userSpaceOnUse"/>',
            '<radialGradient id="f" cx="20.049" cy="-72.168891" r="71.484" fx="32.751" fy="-142.514891" gradientTransform="matrix(0 1 -1.0519 0 0 0)" gradientUnits="userSpaceOnUse"/>',
        ),
    ],
)
def test_apply_gradient_translation(gradient_string, expected_result):
    svg = SVG.fromstring(svg_string(gradient_string))
    for grad_el in svg._select_gradients():
        svg._apply_gradient_translation(grad_el)
    el = svg.xpath_one("//svg:linearGradient | //svg:radialGradient")

    for node in svg.svg_root.getiterator():
        node.tag = etree.QName(node).localname
    etree.cleanup_namespaces(svg.svg_root)

    assert etree.tostring(el).decode("utf-8") == expected_result


@pytest.mark.parametrize(
    "svg_content, expected_result",
    [
        # Blank fill
        # https://github.com/googlefonts/nanoemoji/issues/229
        (
            '<path fill="" d=""/>',
            (SVGPath(),),
        ),
    ],
)
def test_default_for_blank(svg_content, expected_result):
    assert tuple(SVG.fromstring(svg_string(svg_content)).shapes()) == expected_result


@pytest.mark.parametrize(
    "actual, expected_result",
    [
        ("gradient-template-1-before.svg", "gradient-template-1-after.svg"),
        ("gradient-template-2-before.svg", "gradient-template-2-after.svg"),
        ("gradient-template-3-before.svg", "gradient-template-3-after.svg"),
    ],
)
def test_resolve_gradient_templates(actual, expected_result):
    def apply_templates(svg):
        for grad_el in svg._select_gradients():
            svg._apply_gradient_template(grad_el)
        svg._remove_orphaned_gradients()
        return svg

    _test(
        actual,
        expected_result,
        apply_templates,
    )


@pytest.mark.parametrize(
    "actual, expected_result",
    [
        ("nested-svg-slovenian-flag-before.svg", "nested-svg-slovenian-flag-after.svg"),
    ],
)
def test_resolve_nested_svgs(actual, expected_result):
    _test(
        actual,
        expected_result,
        lambda svg: svg.resolve_nested_svgs(),
    )


def test_tostring_pretty_print():
    svg = SVG.fromstring(
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 128 128">\n'
        "<g>  \n"
        "\t  <g>  \r\n"
        '\t\t  <path d="M60,30 L100,30 L100,70 L60,70 Z"/>\n\n'
        "\t  </g>  \r"
        "</g> \n"
        "</svg>"
    )

    assert svg.tostring(pretty_print=False) == (
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 128 128">'
        "<g>"
        "<g>"
        '<path d="M60,30 L100,30 L100,70 L60,70 Z"/>'
        "</g>"
        "</g>"
        "</svg>"
    )

    assert svg.tostring(pretty_print=True) == dedent(
        """\
        <svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 128 128">
          <g>
            <g>
              <path d="M60,30 L100,30 L100,70 L60,70 Z"/>
            </g>
          </g>
        </svg>
        """
    )


@pytest.mark.parametrize(
    "actual, expected_result",
    [
        ("fill-rule-evenodd-before.svg", "fill-rule-evenodd-after.svg"),
    ],
)
def test_evenodd_to_nonzero_winding(actual, expected_result):
    _test(
        actual,
        expected_result,
        lambda svg: svg.evenodd_to_nonzero_winding().round_floats(3, inplace=True),
    )


@pytest.mark.parametrize(
    "input_svg",
    (
        "explicit-default-fill-no-inherit-before.svg",
        "explicit-default-stroke-no-inherit-before.svg",
        "inherit-default-fill-before.svg",
    ),
)
def test_update_tree_lossless(input_svg):
    with open(locate_test_file(input_svg)) as f:
        svg_data = f.read()
    svg = SVG.fromstring(svg_data)
    assert not svg.elements  # initially empty list

    # _elements() parses shapes using from_element, populating self.elements
    _ = svg._elements()
    assert svg.elements

    # _update_etree calls to_element on each shape and resets self.elements
    svg._update_etree()
    assert not svg.elements

    assert svg.tostring(pretty_print=True) == svg_data


def _only(maybe_many):
    if len(maybe_many) != 1:
        raise ValueError(f"Must have exactly 1 item in {maybe_many}")
    return next(iter(maybe_many))


def _subpaths(path: str) -> Tuple[str, ...]:
    return tuple(m.group() for m in re.finditer(r"[mM][^Mm]*", path))


# https://github.com/googlefonts/picosvg/issues/269
# Make sure we drop subpaths that have 0 area after rounding.
def test_shapes_for_stroked_path():
    svg = SVG.parse(locate_test_file("emoji_u1f6d2.svg")).topicosvg()
    path_before = _only(svg.shapes()).as_path().d
    svg = svg.topicosvg()
    path_after = _only(svg.shapes()).as_path().d

    assert len(_subpaths(path_before)) == len(
        _subpaths(path_after)
    ), f"Lost subpaths\n{path_before}\n{path_after}"


@pytest.mark.parametrize("inplace", (True, False))
def test_topicosvg_ndigits(inplace):
    svg = SVG.fromstring(
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 128 128">'
        "<defs/>"
        '<path d="M60.4999,30 L100.06,30 L100.06,70 L60.4999,70 Z"/>'
        "</svg>"
    )
    pico = svg.topicosvg(ndigits=1, inplace=inplace)
    assert pico.tostring() == dedent(
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 128 128">'
        "<defs/>"
        '<path d="M60.5,30 L100.1,30 L100.1,70 L60.5,70 Z"/>'
        "</svg>"
    )


def test_remove_processing_instructions():
    xpacket_svg = load_test_svg("xpacket-before.svg")
    assert "xpacket" in xpacket_svg.tostring()
    pico_svg = xpacket_svg.remove_processing_instructions()
    assert "xpacket" not in pico_svg.tostring()


@pytest.mark.parametrize(
    "svg_string, match_re, expected_passthrough",
    [
        # text element
        (
            """
            <svg xmlns="http://www.w3.org/2000/svg"
                width="512" height="512"
                viewBox="0 0 30 30">
            <text x="20" y="35">Hello</text>
            </svg>
            """,
            r"Unable to convert to picosvg: BadElement: /svg\[0\]/text\[0\]",
            "text",
        ),
        # text with tspan
        (
            """
            <svg xmlns="http://www.w3.org/2000/svg"
                width="512" height="512"
                viewBox="0 0 30 30">
            <text x="20" y="35">
                <tspan x="0" y="20" style="font-style:normal;font-variant:normal;font-weight:normal;font-stretch:normal;font-size:10px;font-variant-ligatures:normal;font-variant-caps:small-caps;font-variant-numeric:normal;font-variant-east-asian:normal;stroke-width:1;">Hello</tspan>
            </text>
            </svg>
            """,
            r"Unable to convert to picosvg: BadElement: /svg\[0\]/text\[0\]",
            "tspan",
        ),
        # text with textPath, sample copied from https://developer.mozilla.org/en-US/docs/Web/SVG/Element/textPath
        (
            """
            <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                <!-- to hide the path, it is usually wrapped in a <defs> element -->
                <!-- <defs> -->
                <path
                    id="MyPath"
                    fill="none"
                    stroke="red"
                    d="M10,90 Q90,90 90,45 Q90,10 50,10 Q10,10 10,40 Q10,70 45,70 Q70,70 75,50" />
                <!-- </defs> -->

                <text>
                    <textPath href="#MyPath">A very long text on path.</textPath>
                </text>
                </svg>
            """,
            r"Unable to convert to picosvg: BadElement: /svg\[0\]/text\[0\]",
            "textPath",
        ),
    ],
)
def test_allow_text(svg_string, match_re, expected_passthrough):
    text_svg = SVG.fromstring(svg_string)
    with pytest.raises(
        ValueError,
        match=match_re,
    ):
        text_svg.topicosvg()
    assert expected_passthrough in text_svg.topicosvg(allow_text=True).tostring()


def test_bounding_box():
    bounding_svg = load_test_svg("bounding.svg")
    bounds = bounding_svg.bounding_box()
    assert math.isclose(bounds.x, 14.22469, abs_tol=1e-5)
    assert math.isclose(bounds.y, 48.57185, abs_tol=1e-5)
    assert math.isclose(bounds.w, 95.64109, abs_tol=1e-5)
    assert math.isclose(bounds.h, 62.20909, abs_tol=1e-5)

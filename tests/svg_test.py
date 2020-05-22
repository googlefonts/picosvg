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
from lxml import etree
import os
import pytest
from picosvg.svg import SVG
from svg_test_helpers import *


def _test(actual, expected_result, op):
    actual = op(load_test_svg(actual))
    expected_result = load_test_svg(expected_result)
    drop_whitespace(actual)
    drop_whitespace(expected_result)
    print(f"A: {pretty_print(actual.toetree())}")
    print(f"E: {pretty_print(expected_result.toetree())}")
    assert actual.tostring() == expected_result.tostring()


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
    svg = SVG.fromstring(shape)
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
        ("<rect width='1' height='1'/>", 'd="M0,0 H1 V1 H0 V0 z"'),
        # rect: sharp corners
        (
            "<rect x='10' y='11' width='17' height='11'/>",
            'd="M10,11 H27 V22 H10 V11 z"',
        ),
        # rect: round corners
        (
            "<rect x='9' y='9' width='11' height='7' rx='2'/>",
            'd="M11,9 H18 A2 2 0 0 1 20,11 V14 A2 2 0 0 1 18,16 H11'
            ' A2 2 0 0 1 9,14 V11 A2 2 0 0 1 11,9 z"',
        ),
        # rect: simple
        (
            "<rect x='11.5' y='16' width='11' height='2'/>",
            'd="M11.5,16 H22.5 V18 H11.5 V16 z"',
        ),
        # polygon
        ("<polygon points='30,10 50,30 10,30'/>", 'd="M30,10 50,30 10,30 z"'),
        # polyline
        ("<polyline points='30,10 50,30 10,30'/>", 'd="M30,10 50,30 10,30"'),
        # circle, minimal valid example
        ("<circle r='1'/>", 'd="M-1,0 A1 1 0 1 1 1,0 A1 1 0 1 1 -1,0 z"'),
        # circle
        (
            "<circle cx='600' cy='200' r='100'/>",
            'd="M500,200 A100 100 0 1 1 700,200 A100 100 0 1 1 500,200 z"',
        ),
        # circle, decimal positioning
        (
            "<circle cx='12' cy='6.5' r='1.5'></circle>",
            'd="M10.5,6.5 A1.5 1.5 0 1 1 13.5,6.5 A1.5 1.5 0 1 1 10.5,6.5 z"',
        ),
        # ellipse
        (
            '<ellipse cx="100" cy="50" rx="100" ry="50"/>',
            'd="M0,50 A100 50 0 1 1 200,50 A100 50 0 1 1 0,50 z"',
        ),
        # ellipse, decimal positioning
        (
            '<ellipse cx="100.5" cy="50" rx="10" ry="50.5"/>',
            'd="M90.5,50 A10 50.5 0 1 1 110.5,50 A10 50.5 0 1 1 90.5,50 z"',
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
    "actual, expected_result",
    [
        ("clip-rect.svg", "clip-rect-clipped.svg"),
        ("clip-ellipse.svg", "clip-ellipse-clipped.svg"),
        ("clip-curves.svg", "clip-curves-clipped.svg"),
        ("clip-multirect.svg", "clip-multirect-clipped.svg"),
        ("clip-groups.svg", "clip-groups-clipped.svg"),
        ("clip-use.svg", "clip-use-clipped.svg"),
    ],
)
def test_apply_clip_path(actual, expected_result):
    _test(actual, expected_result, lambda svg: svg.apply_clip_paths(inplace=True))


@pytest.mark.parametrize(
    "actual, expected_result", [("use-ellipse.svg", "use-ellipse-resolved.svg")]
)
def test_resolve_use(actual, expected_result):
    _test(actual, expected_result, lambda svg: svg.resolve_use(inplace=True))


@pytest.mark.parametrize(
    "actual, expected_result",
    [
        ("ungroup-before.svg", "ungroup-after.svg"),
        ("ungroup-multiple-children-before.svg", "ungroup-multiple-children-after.svg"),
    ],
)
def test_ungroup(actual, expected_result):
    _test(actual, expected_result, lambda svg: svg.ungroup(inplace=True))


@pytest.mark.parametrize(
    "actual, expected_result",
    [
        ("stroke-simplepath-before.svg", "stroke-simplepath-after.svg"),
        ("stroke-capjoinmiterlimit-before.svg", "stroke-capjoinmiterlimit-after.svg"),
    ],
)
def test_strokes_to_paths(actual, expected_result):
    _test(actual, expected_result, lambda svg: svg.strokes_to_paths(inplace=True))


@pytest.mark.parametrize(
    "actual, expected_result", [("rotated-rect.svg", "rotated-rect-after.svg")]
)
def test_transform(actual, expected_result):
    _test(actual, expected_result, lambda svg: svg.apply_transforms(inplace=True))


@pytest.mark.parametrize(
    "actual, expected_result",
    [
        ("ungroup-before.svg", "ungroup-nano.svg"),
        ("ungroup-multiple-children-before.svg", "ungroup-multiple-children-nano.svg"),
        ("group-stroke-before.svg", "group-stroke-nano.svg"),
        ("arcs-before.svg", "arcs-nano.svg"),
        ("invisible-before.svg", "invisible-nano.svg"),
        ("transform-before.svg", "transform-nano.svg"),
        ("group-data-name-before.svg", "group-data-name-after.svg"),
        ("matrix-before.svg", "matrix-nano.svg"),
    ],
)
def test_topicosvg(actual, expected_result):
    _test(actual, expected_result, lambda svg: svg.topicosvg())


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
                "BadElement: /svg[0]/donkey[2]",
                "BadElement: /svg[0]/defs[1]/path[0]",
            ),
        ),
        ("bad-defs-1.svg", ("BadElement: /svg[0]/path[0]",)),
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
            '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="7 7 12 12"/>',
            (7, 7, 12, 12),
        ),
    ],
)
def test_viewbox(svg_string, expected_result):
    assert SVG.fromstring(svg_string).view_box() == expected_result


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

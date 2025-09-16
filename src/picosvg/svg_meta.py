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

import re
from types import MappingProxyType
from lxml import etree  # pytype: disable=import-error
from typing import (
    Any,
    Container,
    Generator,
    Iterable,
    MutableMapping,
    Optional,
    Tuple,
)
from picosvg.geometric_types import Rect


SVGCommand = Tuple[str, Tuple[float, ...]]
SVGCommandSeq = Iterable[SVGCommand]
SVGCommandGen = Generator[SVGCommand, None, None]


def svgns():
    return "http://www.w3.org/2000/svg"


def xlinkns():
    return "http://www.w3.org/1999/xlink"


def splitns(name):
    qn = etree.QName(name)
    return qn.namespace, qn.localname


def strip_ns(tagname):
    return splitns(tagname)[1]


# https://www.w3.org/TR/SVG11/paths.html#PathData
_CMD_ARGS = {
    "m": 2,
    "z": 0,
    "l": 2,
    "h": 1,
    "v": 1,
    "c": 6,
    "s": 4,
    "q": 4,
    "t": 2,
    "a": 7,
}
_CMD_ARGS.update({k.upper(): v for k, v in _CMD_ARGS.items()})


def check_cmd(cmd, args):
    cmd_args = num_args(cmd)
    if cmd_args == 0:
        if args:
            raise ValueError(f"{cmd} has no args, {len(args)} invalid")
    elif len(args) % cmd_args != 0:
        raise ValueError(f"{cmd} has sets of {cmd_args} args, {len(args)} invalid")
    return cmd_args


def num_args(cmd):
    if not cmd in _CMD_ARGS:
        raise ValueError(f'Invalid svg command "{cmd}"')
    return _CMD_ARGS[cmd]


def cmds():
    return _CMD_ARGS.keys()


# For each command iterable of x-coords and iterable of y-coords
# Helpful if you want to adjust them
_CMD_COORDS = {
    "m": ((0,), (1,)),
    "z": ((), ()),
    "l": ((0,), (1,)),
    "h": ((0,), ()),
    "v": ((), (0,)),
    "c": ((0, 2, 4), (1, 3, 5)),
    "s": ((0, 2), (1, 3)),
    "q": ((0, 2), (1, 3)),
    "t": ((0,), (1,)),
    "a": ((5,), (6,)),
}
_CMD_COORDS.update({k.upper(): v for k, v in _CMD_COORDS.items()})


def cmd_coords(cmd):
    if not cmd in _CMD_ARGS:
        raise ValueError(f'Invalid svg command "{cmd}"')
    return _CMD_COORDS[cmd]


def ntos(n: float) -> str:
    # strip superflous .0 decimals
    return str(int(n)) if isinstance(n, float) and n.is_integer() else str(n)


def number_or_percentage(s: str, scale=1) -> float:
    return float(s[:-1]) / 100 * scale if s.endswith("%") else float(s)

def parse_css_length(s: str) -> float:
    """Parse CSS length values with units and convert to float.
    
    Supports common CSS units like px, pt, pc, mm, cm, in, em, rem, %.
    For units that require context (like em, rem), defaults are used.
    
    Args:
        s: String value like '100px', '12pt', '1.5em', '50%'
    
    Returns:
        float: Numeric value converted to pixels (or appropriate base unit)
    """
    if not isinstance(s, str):
        return float(s)
    
    s = s.strip()
    if not s:
        return 0.0
    
    # Handle percentage values
    if s.endswith('%'):
        return float(s[:-1])  # Return percentage as-is, let caller handle scaling
    
    # Common CSS unit conversions to pixels
    # Reference: https://www.w3.org/TR/css-values-3/#absolute-lengths
    unit_conversions = {
        'px': 1.0,      # pixels (base unit)
        'pt': 1.333333, # points: 1pt = 1/72 inch = 1.333333px
        'pc': 16.0,     # picas: 1pc = 12pt = 16px
        'mm': 3.779528, # millimeters: 1mm = 3.779528px
        'cm': 37.79528, # centimeters: 1cm = 37.79528px
        'in': 96.0,     # inches: 1in = 96px
        'em': 16.0,     # em units: default to 16px (typical browser default)
        'rem': 16.0,    # rem units: default to 16px (typical browser default)
        'ex': 8.0,      # ex units: roughly half of em
    }
    
    # Try to extract number and unit
    import re
    match = re.match(r'^([+-]?(?:\d+\.?\d*|\.\d+))([a-zA-Z%]*)$', s)
    if match:
        number_part, unit_part = match.groups()
        number = float(number_part)
        
        if not unit_part:
            # No unit specified, assume pixels
            return number
        
        unit = unit_part.lower()
        if unit in unit_conversions:
            return number * unit_conversions[unit]
        else:
            # Unknown unit, return the number as-is
            return number
    
    # If no match, try to parse as plain number
    try:
        return float(s)
    except ValueError:
        # If all else fails, return 0
        return 0.0

def path_segment(cmd, *args):
    # put commas between coords, spaces otherwise, author readability pref
    args_per_cmd = check_cmd(cmd, args)
    args = [ntos(a) for a in args]
    combined_args = []
    xy_coords = set(zip(*_CMD_COORDS[cmd]))
    if args_per_cmd:
        for n in range(len(args) // args_per_cmd):
            sub_args = args[n * args_per_cmd : (n + 1) * args_per_cmd]
            i = 0
            while i < len(sub_args):
                if (i, i + 1) in xy_coords:
                    combined_args.append(f"{sub_args[i]},{sub_args[i+1]}")
                    i += 2
                else:
                    combined_args.append(sub_args[i])
                    i += 1
    return cmd + " ".join(combined_args)


def parse_css_declarations(
    style: str,
    output: MutableMapping[str, Any],
    property_names: Optional[Container[str]] = None,
) -> str:
    """Parse CSS declaration list into {property: value} XML element attributes.

    Args:
        style: CSS declaration list without the enclosing braces,
            as found in an SVG element's "style" attribute.
        output: a dictionary or lxml.etree._Attrib where to store the parsed properties.
            Note that lxml validates the attribute names and if a given CSS property name
            is not a valid XML name (e.g. vendor specific keywords starting with a hyphen,
            e.g. "-inkscape-font-specification"), it will be silently ignored.
        property_names: optional set of property names to limit the declarations
            to be parsed; if not provided, all will be parsed.

    Returns:
        A string containing the unparsed style declarations, if any.

    Raises:
        ValueError if CSS declaration is invalid and can't be parsed.

    References:
    https://www.w3.org/TR/SVG/styling.html#ElementSpecificStyling
    https://www.w3.org/TR/2013/REC-css-style-attr-20131107/#syntax
    """
    unparsed = []
    for declaration in style.split(";"):
        declaration = declaration.strip()
        if declaration.count(":") == 1:
            property_name, value = declaration.split(":")
            property_name, value = property_name.strip(), value.strip()
            if property_names is None or property_name in property_names:
                try:
                    output[property_name] = value
                except ValueError:
                    # lxml raises if attrib name is invalid (e.g. starts with '-')
                    unparsed.append(declaration)
            else:
                unparsed.append(declaration)
        elif declaration.strip():
            raise ValueError(f"Invalid CSS declaration syntax: {declaration}")
    return "; ".join(unparsed) + ";" if unparsed else ""


def parse_view_box(s: str) -> Rect:
    box = tuple(float(v) for v in re.split(r",|\s+", s))
    if len(box) != 4:
        raise ValueError(f"Unable to parse viewBox: {s!r}")
    return Rect(*box)


# sentinel object to check if special linked fields such as fx/fy are explicitly set;
# using a float type instead of None to make the typechecker happy, and also so that one
# doesn't need to unwrap Optional type whenever accessing those fields
class _LinkedDefault(float):
    def __new__(cls, attr_name):
        self = float.__new__(cls, "NaN")
        self.attr_name = attr_name
        return self

    def __call__(self, data_obj):
        return getattr(data_obj, self.attr_name)


# makes dict read-only
ATTRIB_DEFAULTS = MappingProxyType(
    {
        "clip-path": "",
        "clip-rule": "nonzero",
        "fill": "black",
        "fill-opacity": 1.0,
        "fill-rule": "nonzero",
        "stroke": "none",
        "stroke-width": 1.0,
        "stroke-linecap": "butt",
        "stroke-linejoin": "miter",
        "stroke-miterlimit": 4,
        "stroke-dasharray": "none",
        "stroke-dashoffset": 0.0,
        "stroke-opacity": 1.0,
        "opacity": 1.0,
        "transform": "",
        "style": "",
        "display": "inline",
        "d": "",
        "id": "",
    }
)


def attrib_default(name: str, default: Any = ()) -> Any:
    if name in ATTRIB_DEFAULTS:
        return ATTRIB_DEFAULTS[name]
    if default == ():
        raise ValueError(f"No entry for '{name}' and no default given")
    return default

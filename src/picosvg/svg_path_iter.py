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
from typing import Generator, Tuple
from picosvg import svg_meta

_CMD_RE = re.compile(f'([{"".join(svg_meta.cmds())}])')
_SEPARATOR_RE = re.compile("[, ]+")
_FLOAT_RE = re.compile(
    r"[-+]?"  # optional sign
    r"(?:"
    r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?"  # int or float
    r"|"
    r"(?:\.[0-9]+)"  # float with leading dot (e.g. '.42')
    r")"
    r"(?:[eE][-+]?[0-9]+)?"  # optional scientific notiation
)
_BOOL_RE = re.compile("^[01]")
_ARC_ARGUMENT_TYPES = (
    (float, _FLOAT_RE),  # rx
    (float, _FLOAT_RE),  # ry
    (float, _FLOAT_RE),  # x-axis-rotation
    (int, _BOOL_RE),  # large-arc-flag
    (int, _BOOL_RE),  # sweep-flag
    (float, _FLOAT_RE),  # x
    (float, _FLOAT_RE),  # y
)

# https://www.w3.org/TR/SVG11/paths.html#PathDataMovetoCommands
# If a moveto is followed by multiple pairs of coordinates,
# the subsequent pairs are treated as implicit lineto commands
_IMPLICIT_REPEAT_CMD = {"m": "l", "M": "L"}


def _parse_args(cmd: str, args: str) -> Generator[float, None, None]:
    raw_args = [s for s in _SEPARATOR_RE.split(args) if s]
    if not raw_args:
        return

    if cmd.upper() == "A":
        arg_types = _ARC_ARGUMENT_TYPES
    else:
        arg_types = ((float, _FLOAT_RE),)
    n = len(arg_types)

    i = j = 0
    while j < len(raw_args):
        arg = raw_args[j]
        # modulo to wrap around
        converter, regex = arg_types[i % n]
        m = regex.match(arg)
        if not m:
            raise ValueError(f"Invalid argument #{i} for '{cmd}': {arg!r}")

        start, end = m.span()
        yield converter(arg[start:end])

        if end < len(arg):
            raw_args[j] = arg[end:]
        else:
            j += 1
        i += 1


def _explode_cmd(args_per_cmd, cmd, args):
    cmds = []
    for i in range(len(args) // args_per_cmd):
        if i > 0:
            cmd = _IMPLICIT_REPEAT_CMD.get(cmd, cmd)
        cmds.append((cmd, tuple(args[i * args_per_cmd : (i + 1) * args_per_cmd])))
    return cmds


def parse_svg_path(
    svg_path: str, exploded: bool = False
) -> Generator[Tuple[str, Tuple[float, ...]], None, None]:
    """Parses an svg path.

    Exploded means when params repeat each the command is reported as
    if multiplied. For example "M1,1 2,2 3,3" would report as three
    separate steps when exploded.

    Yields tuples of (cmd, (args))."""
    command_tuples = []
    parts = _CMD_RE.split(svg_path)[1:]
    for i in range(0, len(parts), 2):
        cmd = parts[i]
        raw_args = parts[i + 1].strip()

        args = tuple(_parse_args(cmd, raw_args))

        args_per_cmd = svg_meta.check_cmd(cmd, args)
        if args_per_cmd == 0 or not exploded:
            command_tuples.append((cmd, args))
        else:
            command_tuples.extend(_explode_cmd(args_per_cmd, cmd, args))
    for t in command_tuples:
        yield t

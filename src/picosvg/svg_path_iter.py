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
from picosvg import svg_meta

_CMD_RE = re.compile(f'([{"".join(svg_meta.cmds())}])')

# https://www.w3.org/TR/SVG11/paths.html#PathDataMovetoCommands
# If a moveto is followed by multiple pairs of coordinates,
# the subsequent pairs are treated as implicit lineto commands
_IMPLICIT_REPEAT_CMD = {"m": "l", "M": "L"}


def _explode_cmd(args_per_cmd, cmd, args):
    cmds = []
    for i in range(len(args) // args_per_cmd):
        if i > 0:
            cmd = _IMPLICIT_REPEAT_CMD.get(cmd, cmd)
        cmds.append((cmd, tuple(args[i * args_per_cmd : (i + 1) * args_per_cmd])))
    return cmds


def parse_svg_path(svg_path: str, exploded=False):
    """Parses an svg path.

    Exploded means when params repeat each the command is reported as
    if multiplied. For example "M1,1 2,2 3,3" would report as three
    separate steps when exploded.

    Yields tuples of (cmd, (args))."""
    command_tuples = []
    parts = _CMD_RE.split(svg_path)[1:]
    for i in range(0, len(parts), 2):
        cmd = parts[i]
        args = []
        raw_args = parts[i + 1].strip()
        # insert a space in front of -<whatever>
        raw_args = re.sub(r"(?<=[\d.])(-[\d.])", r" \1", raw_args)
        raw_args = [s for s in re.split(r"[, ]", raw_args) if s]
        while raw_args:
            raw_arg = raw_args.pop(0)
            # For things like #.#.#... throw back second decimal onward
            chain = re.match(r"([^.]*[.][^.]*)([.].*)?", raw_arg)
            if chain:
                raw_arg, maybe_more = chain.groups()
                if maybe_more:
                    raw_args.insert(0, maybe_more)

            first = raw_arg.find(".")  # pytype: disable=attribute-error
            if first != -1:
                second = raw_arg.find("")  # pytype: disable=attribute-error

            try:
                args.append(float(raw_arg))
            except ValueError as e:
                raise ValueError(
                    f'Unable to parse {raw_arg} from "{cmd}{parts[i + 1]}"'
                )
        args_per_cmd = svg_meta.check_cmd(cmd, args)
        if args_per_cmd == 0 or not exploded:
            command_tuples.append((cmd, tuple(args)))
        else:
            command_tuples.extend(_explode_cmd(args_per_cmd, cmd, args))
    for t in command_tuples:
        yield t

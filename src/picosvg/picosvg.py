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

"""Simplify svg.

Usage:
picosvg.py emoji_u1f469_1f3fd_200d_1f91d_200d_1f468_1f3fb.svg
<simplified svg dumped to stdout>
"""
from absl import app
from absl import flags
from lxml import etree  # pytype: disable=import-error
from picosvg.svg import SVG
from picosvg.svg_meta import svgns
import sys


FLAGS = flags.FLAGS


flags.DEFINE_bool("clip_to_viewbox", False, "Whether to clip content outside viewbox")
flags.DEFINE_string("output_file", "-", "Output SVG file ('-' means stdout)")


def _reduce_text(text):
    text = text.strip() if text else None
    return text if text else None


def _run(argv):
    try:
        input_file = argv[1]
    except IndexError:
        input_file = None

    if input_file:
        svg = SVG.parse(input_file).topicosvg()
    else:
        svg = SVG.fromstring(sys.stdin.read()).topicosvg()

    if FLAGS.clip_to_viewbox:
        svg.clip_to_viewbox(inplace=True)

    tree = svg.toetree()

    # lxml really likes to retain whitespace
    for e in tree.iter("*"):
        e.text = _reduce_text(e.text)
        e.tail = _reduce_text(e.tail)

    output = etree.tostring(tree, pretty_print=True).decode("utf-8")

    if FLAGS.output_file == "-":
        print(output)
    else:
        with open(FLAGS.output_file, "w") as f:
            f.write(output)


def main(argv=None):
    # We don't seem to be __main__ when run as cli tool installed by setuptools
    app.run(_run, argv=argv)


if __name__ == "__main__":
    main()

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
from lxml import etree  # pytype: disable=import-error
from picosvg.svg import SVG
from picosvg.svg_meta import svgns
import sys


def _reduce_text(text):
    text = text.strip() if text else None
    return text if text else None


def main():
    svg = SVG.parse(sys.argv[1]).topicosvg()

    tree = svg.toetree()

    # lxml really likes to retain whitespace
    for e in tree.iter("*"):
        e.text = _reduce_text(e.text)
        e.tail = _reduce_text(e.tail)

    print(etree.tostring(tree, pretty_print=True).decode("utf-8"))


if __name__ == "__main__":
    main()

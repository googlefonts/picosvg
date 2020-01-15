"""Simplify svg.

Usage:
simplify.py an_svg.svg
<simplified svg dumped to stdout>
"""
from lxml import etree
from svg import SVG
import sys

def _reduce_text(text):
  text = text.strip() if text else None
  return text if text else None


def main():
  svg = SVG.parse(sys.argv[1])
  svg.shapes_to_paths(inplace=True)
  svg.resolve_use(inplace=True)
  svg.apply_clip_paths(inplace=True)

  # TODO ungroup
  # TODO destroy defs
  # TODO gather all used gradients together, perhaps to a single top defs

  # lxml really likes to retain whitespace
  tree = svg.toetree()
  for e in tree.iter('*'):
    e.text = _reduce_text(e.text)
    e.tail = _reduce_text(e.tail)

  print(etree.tostring(tree, pretty_print=True).decode('utf-8'))

if __name__== '__main__':
  main()

"""Simplify svg.

Usage:
simplify.py emoji_u1f469_1f3fd_200d_1f91d_200d_1f468_1f3fb.svg
<simplified svg dumped to stdout>
"""
from lxml import etree
from svg import SVG
from svg_meta import svgns
import sys

def _reduce_text(text):
  text = text.strip() if text else None
  return text if text else None


def main():
  svg = (SVG.parse(sys.argv[1])
         .tonanosvg())

  tree = svg.toetree()

  # lxml really likes to retain whitespace
  for e in tree.iter('*'):
    e.text = _reduce_text(e.text)
    e.tail = _reduce_text(e.tail)

  print(etree.tostring(tree, pretty_print=True).decode('utf-8'))

if __name__== '__main__':
  main()

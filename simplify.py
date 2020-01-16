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

  # destroy defs
  for def_el in [e for e in tree.xpath('//svg:defs', namespaces={'svg': svgns()})]:
    def_el.getparent().remove(def_el)

  # gather gradients together, perhaps to a single top defs
  defs = etree.Element('defs')
  tree.insert(0, defs)
  for gradient in tree.xpath('//svg:linearGradient | //svg:radialGradient',
                             namespaces={'svg': svgns()}):
    gradient.getparent().remove(gradient)
    defs.append(gradient)

  # lxml really likes to retain whitespace
  for e in tree.iter('*'):
    e.text = _reduce_text(e.text)
    e.tail = _reduce_text(e.tail)

  print(etree.tostring(tree, pretty_print=True).decode('utf-8'))

if __name__== '__main__':
  main()

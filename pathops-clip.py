from lxml import etree
import svg_ops


def main():
  svg_original = etree.parse('clip-me.svg')
  svg_paths = svg_ops.replace_shapes_with_paths(svg_original)
  print(etree.tostring(svg_paths, pretty_print=True).decode('utf-8'))

if __name__ == '__main__':
  main()

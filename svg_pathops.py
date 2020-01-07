"""SVGPath <=> skia-pathops constructs to enable ops on paths."""
import pathops
from svg_types import SVGPath, SVGShape

# Absolutes only
_SVG_CMD_TO_SKIA_FN = {
  'M': pathops.Path.moveTo,
  'L': pathops.Path.lineTo,
  'Q': pathops.Path.quadTo,
  'Z': pathops.Path.close,
  # TODO 'C': ,
  # TODO 'S': ,
  # TODO 'T': ,
  # TODO 'A': ,
}

_SKIA_CMD_TO_SVG_CMD = {
  'moveTo': 'M',
  'lineTo': 'L',
  'quadTo': 'Q',
  'closePath': 'Z',
}

def skia_path(shape: SVGShape):
  path = (shape.as_path()
          .explicit_lines()  # hHvV => lL
          .absolute(inplace=True))

  sk_path = pathops.Path()
  for cmd, args in path:
    if cmd not in _SVG_CMD_TO_SKIA_FN:
      raise ValueError(f'No mapping to Skia for "{cmd}"')
    _SVG_CMD_TO_SKIA_FN[cmd](sk_path, *args)

  return sk_path

def svg_path(skia_path: pathops.Path):
  path = SVGPath()
  for cmd, arg_tuples in skia_path.segments:
    if cmd not in _SKIA_CMD_TO_SVG_CMD:
      raise ValueError(f'No mapping to svg for "{cmd}"')
    cmd = _SKIA_CMD_TO_SVG_CMD[cmd]
    for arg_tuple in arg_tuples:
      path._add_cmd(cmd, *arg_tuple)
    if not arg_tuples:
      path._add_cmd(cmd)
  return path

def _do_pathop(op, svg_shapes):
  op_builder = pathops.OpBuilder()
  for svg_shape in svg_shapes:
    sk_path = skia_path(svg_shape)
    op_builder.add(sk_path, op)
  result = op_builder.resolve()
  return svg_path(result)

def union(svg_shapes):
  return _do_pathop(pathops.PathOp.UNION, svg_shapes)

def intersection(svg_shapes):
  return _do_pathop(pathops.PathOp.INTERSECTION, svg_shapes)

import re
import svg_meta

_CMD_RE = re.compile(f'([{"".join(svg_meta.cmds())}])')

# https://www.w3.org/TR/SVG11/paths.html#PathDataMovetoCommands
# If a moveto is followed by multiple pairs of coordinates,
# the subsequent pairs are treated as implicit lineto commands
_IMPLICIT_REPEAT_CMD = {
  'm': 'l',
  'M': 'L'
}

def _explode_cmd(args_per_cmd, cmd, args):
  cmds = []
  for i in range(len(args) // args_per_cmd):
    if i > 0:
      cmd = _IMPLICIT_REPEAT_CMD.get(cmd, cmd)
    cmds.append((cmd, tuple(args[i * args_per_cmd:(i + 1) * args_per_cmd])))
  return cmds

def _parse_svg_path(svg_path: str, exploded=False):
  """Parses an svg path to tuples of (cmd, (args))"""
  command_tuples = []
  parts = _CMD_RE.split(svg_path)[1:]
  for i in range(0, len(parts), 2):
    cmd = parts[i]
    args = []
    raw_args = [s for s in re.split(r'[, ]|(?=-)', parts[i + 1].strip()) if s]
    for raw_arg in raw_args:
      try:
        args.append(float(raw_arg))
      except ValueError as e:
        raise ValueError(f'Unable to parse {raw_arg} from "{cmd}{parts[i + 1]}"')
    args_per_cmd = svg_meta.check_cmd(cmd, args)
    if args_per_cmd == 0 or not exploded:
      command_tuples.append((cmd, tuple(args)))
    else:
      command_tuples.extend(_explode_cmd(args_per_cmd, cmd, args))
  return command_tuples

class SVGPathIter:
  """Iterates commands, optionally in exploded form.

  Exploded means when params repeat each the command is reported as
  if multiplied. For example "M1,1 2,2 3,3" would report as three
  separate steps when exploded.
  """
  def __init__(self, path: str, exploded=False):
    self.cmds = _parse_svg_path(path, exploded=exploded)
    self.cmd_idx = -1

  def __iter__(self):
    return self

  def __next__(self):
    self.cmd_idx += 1
    if self.cmd_idx >= len(self.cmds):
      raise StopIteration()
    return self.cmds[self.cmd_idx]

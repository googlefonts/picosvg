import re


def svgns():
    return "http://www.w3.org/2000/svg"


# https://www.w3.org/TR/SVG11/paths.html#PathData
_CMD_ARGS = {
    "m": 2,
    "z": 0,
    "l": 2,
    "h": 1,
    "v": 1,
    "c": 6,
    "s": 4,
    "q": 4,
    "t": 2,
    "a": 7,
}
_CMD_ARGS.update({k.upper(): v for k, v in _CMD_ARGS.items()})


def check_cmd(cmd, args):
    cmd_args = num_args(cmd)
    if cmd_args == 0:
        if args:
            raise ValueError(f"{cmd} has no args, {len(args)} invalid")
    elif len(args) % cmd_args != 0:
        raise ValueError(f"{cmd} has sets of {cmd_args} args, {len(args)} invalid")
    return cmd_args


def num_args(cmd):
    if not cmd in _CMD_ARGS:
        raise ValueError(f'Invalid svg command "{cmd}"')
    return _CMD_ARGS[cmd]


def cmds():
    return _CMD_ARGS.keys()


# For each command iterable of x-coords and iterable of y-coords
# Helpful if you want to adjust them
_CMD_COORDS = {
    "m": ((0,), (1,)),
    "z": ((), ()),
    "l": ((0,), (1,)),
    "h": ((0,), ()),
    "v": ((), (0,)),
    "c": ((0, 2, 4), (1, 3, 5)),
    "s": ((0, 2), (1, 3)),
    "q": ((0, 2), (1, 3)),
    "t": ((0,), (1,)),
    "a": ((5,), (6,)),
}
_CMD_COORDS.update({k.upper(): v for k, v in _CMD_COORDS.items()})


def cmd_coords(cmd):
    if not cmd in _CMD_ARGS:
        raise ValueError(f'Invalid svg command "{cmd}"')
    return _CMD_COORDS[cmd]


def ntos(n):
    # %f likes to add unnecessary 0's, %g isn't consistent about # decimals
    return ("%.3f" % n).rstrip("0").rstrip(".")


def path_segment(cmd, *args):
    # put commas between coords, spaces otherwise, author readability pref
    cmd_args = check_cmd(cmd, args)
    args = [ntos(a) for a in args]
    combined_args = []
    xy_coords = set(zip(*_CMD_COORDS[cmd]))
    i = 0
    while i < len(args):
        if (i, i + 1) in xy_coords:
            combined_args.append(f"{args[i]},{args[i+1]}")
            i += 2
        else:
            combined_args.append(args[i])
            i += 1
    return cmd + " ".join(combined_args)

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

# Functions meant to help discern if shapes are the same or not.

import copy
import dataclasses
from math import atan2
from picosvg.geometric_types import Vector, almost_equal
from picosvg.svg_types import SVGShape, SVGPath
from typing import Optional, Tuple
from picosvg import svg_meta
from picosvg.svg_transform import Affine2D


# Number of decimal digits to round floats when normalizing or comparing
# TODO: hard to get #s to line up well with high tolerance
# TODO: maybe the input svgs should have higher precision? - only 2 decimals on hearts
_DEFAULT_TOLERANCE = 6
_ROUND_RANGE = range(3, 13)  # range of rounds to try


def _first_move(path: SVGPath) -> Tuple[float, float]:
    cmd, args = next(iter(path))
    if cmd.upper() != "M":
        raise ValueError(f"Path for {path} should start with a move")
    return args


def _vectors(path: SVGPath) -> Vector:
    for cmd, args in path:
        x_coord_idxs, y_coord_idxs = svg_meta.cmd_coords(cmd)
        if cmd.lower() == "z":
            return Vector(0., 0.)
        yield Vector(args[x_coord_idxs[-1]], args[y_coord_idxs[-1]])


def _nth_vector(path: SVGPath, n: int) -> Vector:
    vectors = _vectors(path)
    for _ in range(n):
        next(vectors)
    return next(vectors)


def _angle(v: Vector) -> float:
    # gives the directional angle of vector (unlike acos)
    return atan2(v.y, v.x)


def _affine_vec2vec(initial: Vector, target: Vector) -> Affine2D:
    affine = Affine2D.identity()

    # rotate initial to have the same angle as target (may have different magnitude)
    angle = _angle(target) - _angle(initial)
    affine = Affine2D.identity().rotate(angle)
    vec = affine.map_vector(initial)

    # scale to target magnitude
    s = target.norm() / vec.norm()

    affine = Affine2D.product(Affine2D.identity().scale(s, s), affine)

    return affine


# Makes a shape safe for a walk with _affine_callback
def _affine_friendly(shape: SVGShape) -> SVGPath:
    path = shape.as_path()
    if shape is path:
        path = copy.deepcopy(path)
    return (path
        .relative(inplace=True)
        .explicit_lines(inplace=True)
        .expand_shorthand(inplace=True))


# Transform all coords in an affine-friendly path
def _affine_callback(affine, subpath_start, curr_pos, cmd, args, *_unused):
    x_coord_idxs, y_coord_idxs = svg_meta.cmd_coords(cmd)
    # hard to do things like rotate if we have 1d coords
    assert len(x_coord_idxs) == len(y_coord_idxs), f"{cmd}, {args}"

    args = list(args)  # we'd like to mutate 'em
    for x_coord_idx, y_coord_idx in zip(x_coord_idxs, y_coord_idxs):
        if cmd == cmd.upper():
            # for an absolute cmd allow translation: map_point
            new_x, new_y = affine.map_point((args[x_coord_idx], args[y_coord_idx]))
        else:
            # for a relative coord no translate: map_vector
            new_x, new_y = affine.map_vector((args[x_coord_idx], args[y_coord_idx]))

        if almost_equal(new_x, 0):
            new_x = 0
        if almost_equal(new_y, 0):
            new_y = 0
        args[x_coord_idx] = new_x
        args[y_coord_idx] = new_y
    return ((cmd, args),)


def normalize(shape: SVGShape, tolerance: int = _DEFAULT_TOLERANCE) -> SVGShape:
    """Build a version of shape that will compare == to other shapes even if offset.

    Intended use is to normalize multiple shapes to identify opportunity for reuse."""

    path = _affine_friendly(dataclasses.replace(shape, id=""))

    # Make path relative, with first coord at 0,0
    x, y = _first_move(path)
    path.move(-x, -y, inplace=True)

    # By normalizing vector 1 to [1 0] and making first move off y positive we
    # normalize away rotation, scale and shear.
    vec1 = _nth_vector(path, 1)  # ignore M 0,0
    path.walk(lambda *args: _affine_callback(_affine_vec2vec(vec1, Vector(1, 0)), *args))

    # TODO instead of flipping normalize vec2 to [0 1]?
    # Would be nice to avoid destroying the initial [1 0]
    # If we just compute another affine it probably will wreck that
    flip = False
    for vec in _vectors(path):
        if vec.y != 0:
            flip = vec.y < 0
            break

    if flip:
        path.walk(lambda *args: _affine_callback(Affine2D.flip_y(), *args))

    # TODO: what if shapes are the same but different start point

    path.round_floats(tolerance, inplace=True)
    return path


def affine_between(
    s1: SVGShape, s2: SVGShape, tolerance: int = _DEFAULT_TOLERANCE
) -> Optional[Affine2D]:
    """Returns the Affine2D to change s1 into s2 or None if no solution was found.

    Intended use is to call this only when the normalized versions of the shapes
    are the same, in which case finding a solution is typical

    """
    def _try_affine(affine, s1, s2):
        maybe_match = copy.deepcopy(s1)
        maybe_match.walk(lambda *args: _affine_callback(affine, *args))
        return maybe_match.almost_equals(s2, tolerance)

    def _round(affine, s1, s2):
        # TODO bsearch?
        for i in _ROUND_RANGE:
            rounded = affine.round(i)
            if _try_affine(rounded, s1, s2):
                return rounded
        return affine  # give up

    s1 = dataclasses.replace(s1, id="")
    s2 = dataclasses.replace(s2, id="")

    if s1.almost_equals(s2, tolerance):
        return Affine2D.identity()

    s1 = _affine_friendly(s1)
    s2 = _affine_friendly(s2)

    s1x, s1y = _first_move(s1)
    s2x, s2y = _first_move(s2)

    affine = Affine2D.identity().translate(s2x - s1x, s2y - s1y)
    if _try_affine(affine, s1, s2):
        return affine

    # TODO how to share code with normalize?

    # Normalize first edge. This may leave s1 as the mirror of s2 over that edge.
    s1_vec1 = _nth_vector(s1, 1)
    s2_vec1 = _nth_vector(s2, 1)

    transforms = [
        # Move to 0,0
        Affine2D.identity().translate(-s1x, -s1y),
        # Normalize vector1
        _affine_vec2vec(s1_vec1, s2_vec1),
        # Move to s2 start
        Affine2D.identity().translate(s2x, s2y)
    ]
    affine = Affine2D.compose_ltr(transforms)

    # TODO if that doesn't fix vec1 we can give up
    # TODO just testing vec2 would tell us if we should try mirroring
    if _try_affine(affine, s1, s2):
        return _round(affine, s1, s2)

    # Last chance, try to mirror
    transforms = (
        # Normalize vector 1
        transforms[:-1]
        + [
            # Rotate first edge to lie on y axis
            Affine2D.identity().rotate(-_angle(s2_vec1)),
            Affine2D.flip_y(),
            # Rotate back into position
            Affine2D.identity().rotate(_angle(s2_vec1)),
        ]
        # Move to s2's start point
        + transforms[-1:])

    affine = Affine2D.compose_ltr(transforms)
    if _try_affine(affine, s1, s2):
        return _round(affine, s1, s2)

    # If we still aren't the same give up
    return None

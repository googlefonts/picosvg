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
from itertools import islice
from math import atan2
from picosvg.geometric_types import Vector, almost_equal
from picosvg.svg_types import SVGShape, SVGPath
from typing import Generator, Iterable, Optional, Tuple
from picosvg import svg_meta
from picosvg.svg_transform import Affine2D


_SIGNIFICANCE_FACTOR = 5  # Must be at least N x tolerance to be significant
_ROUND_RANGE = range(3, 13)  # range of rounds to try


def _first_move(path: SVGPath) -> Tuple[float, float]:
    cmd, args = next(iter(path))
    if cmd.upper() != "M":
        raise ValueError(f"Path for {path} should start with a move")
    return args


def _vectors(path: SVGPath) -> Generator[Vector, None, None]:
    for cmd, args in path:
        x_coord_idxs, y_coord_idxs = svg_meta.cmd_coords(cmd)
        if cmd.lower() == "z":
            yield Vector(0.0, 0.0)
        else:
            yield Vector(args[x_coord_idxs[-1]], args[y_coord_idxs[-1]])


def _nth_vector(path: SVGPath, n: int) -> Vector:
    return next(islice(_vectors(path), n, n + 1))


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
    s = 0
    if vec.norm() != 0:
        s = target.norm() / vec.norm()

    affine = Affine2D.compose_ltr((affine, Affine2D.identity().scale(s, s)))

    return affine


def _first_y(vectors: Iterable[Vector], tolerance: float) -> Optional[Vector]:
    tolerance = _SIGNIFICANCE_FACTOR * tolerance
    for idx, vec in enumerate(vectors):
        if idx > 0 and abs(vec.y) > tolerance:
            return vec
    return None


# Makes a shape safe for a walk with _affine_callback
def _affine_friendly(shape: SVGShape) -> SVGPath:
    path = shape.as_path()
    if shape is path:
        path = copy.deepcopy(path)
    return (
        path.relative(inplace=True)
        .explicit_lines(inplace=True)
        .expand_shorthand(inplace=True)
    )


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


def normalize(shape: SVGShape, tolerance: float) -> SVGShape:
    """Build a version of shape that will compare == to other shapes even if offset,
    scaled, rotated, etc.

    Intended use is to normalize multiple shapes to identify opportunity for reuse."""

    path = _affine_friendly(dataclasses.replace(shape, id=""))

    # Make path relative, with first coord at 0,0
    x, y = _first_move(path)
    path.move(-x, -y, inplace=True)

    # Normlize vector 1 to [1 0]; eliminates rotation and uniform scaling
    vec1 = _nth_vector(path, 1)  # ignore M 0,0
    affine1 = _affine_vec2vec(vec1, Vector(1, 0))
    path.walk(lambda *args: _affine_callback(affine1, *args))

    # Scale first y movement to 1.0
    vecy = _first_y(_vectors(path), tolerance)
    if vecy and not almost_equal(vecy.y, 1.0):
        affine2 = Affine2D.identity().scale(1, 1 / vecy.y)
        path.walk(lambda *args: _affine_callback(affine2, *args))

    # TODO: what if shapes are the same but different start point
    # TODO: what if shapes are the same but different drawing cmds
    # This DOES happen in Noto; extent unclear

    path.round_multiple(tolerance, inplace=True)
    return path


def _apply_affine(affine: Affine2D, s: SVGPath) -> SVGPath:
    s_prime = copy.deepcopy(s)
    s_prime.walk(lambda *args: _affine_callback(affine, *args))
    return s_prime


def _try_affine(affine: Affine2D, s1: SVGPath, s2: SVGPath, tolerance: float):
    return _apply_affine(affine, s1).almost_equals(s2, tolerance)


def _round(affine, s1, s2, tolerance):
    # TODO bsearch?
    for i in _ROUND_RANGE:
        rounded = affine.round(i)
        if _try_affine(rounded, s1, s2, tolerance):
            return rounded
    return affine  # give up


def affine_between(s1: SVGShape, s2: SVGShape, tolerance: float) -> Optional[Affine2D]:
    """Returns the Affine2D to change s1 into s2 or None if no solution was found.

    Intended use is to call this only when the normalized versions of the shapes
    are the same, in which case finding a solution is typical

    """
    s1 = dataclasses.replace(s1, id="")
    s2 = dataclasses.replace(s2, id="")

    if s1.almost_equals(s2, tolerance):
        return Affine2D.identity()

    s1 = _affine_friendly(s1)
    s2 = _affine_friendly(s2)

    s1x, s1y = _first_move(s1)
    s2x, s2y = _first_move(s2)

    affine = Affine2D.identity().translate(s2x - s1x, s2y - s1y)
    if _try_affine(affine, s1, s2, tolerance):
        return affine

    # Normalize first edge.
    # Fixes rotation, x-scale, and uniform scaling.
    s1_vec1 = _nth_vector(s1, 1)
    s2_vec1 = _nth_vector(s2, 1)

    s1_to_origin = Affine2D.identity().translate(-s1x, -s1y)
    s2_to_origin = Affine2D.identity().translate(-s2x, -s2y)
    s1_vec1_to_s2_vec1 = _affine_vec2vec(s1_vec1, s2_vec1)

    # Move to s2 start
    origin_to_s2 = Affine2D.identity().translate(s2x, s2y)

    affine = Affine2D.compose_ltr((s1_to_origin, s1_vec1_to_s2_vec1, origin_to_s2))
    if _try_affine(affine, s1, s2, tolerance):
        return _round(affine, s1, s2, tolerance)

    # Could be non-uniform scaling and/or mirroring
    # Scale first y movement (after matching up vec1) to match

    # Rotate first edge to lie on x axis
    s2_vec1_angle = _angle(s2_vec1)
    rotate_s2vec1_onto_x = Affine2D.identity().rotate(-s2_vec1_angle)
    rotate_s2vec1_off_x = Affine2D.identity().rotate(s2_vec1_angle)

    affine = Affine2D.compose_ltr(
        (s1_to_origin, s1_vec1_to_s2_vec1, rotate_s2vec1_onto_x)
    )
    s1_prime = _apply_affine(affine, s1)

    affine = Affine2D.compose_ltr((s2_to_origin, rotate_s2vec1_onto_x))
    s2_prime = _apply_affine(affine, s2)

    s1_vecy = _first_y(_vectors(s1_prime), tolerance)
    s2_vecy = _first_y(_vectors(s2_prime), tolerance)

    if s1_vecy and s2_vecy:
        affine = Affine2D.compose_ltr(
            (
                s1_to_origin,
                s1_vec1_to_s2_vec1,
                # lie vec1 along x axis
                rotate_s2vec1_onto_x,
                # scale first y-vectors to match; x-parts should already match
                Affine2D.identity().scale(1.0, s2_vecy.y / s1_vecy.y),
                # restore the rotation we removed
                rotate_s2vec1_off_x,
                # drop into final position
                origin_to_s2,
            )
        )
        if _try_affine(affine, s1, s2, tolerance):
            return _round(affine, s1, s2, tolerance)

    # If we still aren't the same give up
    return None

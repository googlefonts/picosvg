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

from picosvg.geometric_types import Point, Rect, Vector
import pytest


def test_point_subtraction_and_addition():
    p0 = Point(1, 3)
    p1 = Point(-2, 4)

    v = p1 - p0

    assert isinstance(v, Vector)
    assert v.x == -3
    assert v.y == 1

    p2 = p1 - v

    assert isinstance(p2, Point)
    assert p2 == p0

    p3 = p0 + v
    assert isinstance(p3, Point)
    assert p3 == p1


class TestVector:
    def test_multiply(self):
        v = Vector(3, 4)
        assert v * 2 == Vector(6, 8)
        assert v * 0.5 == Vector(1.5, 2)
        assert 3 * v == Vector(9, 12)
        assert 1.5 * v == Vector(4.5, 6)

        with pytest.raises(TypeError):
            _ = v * "a"

    def test_perpendicular(self):
        v = Vector(-3, 5)

        assert v.perpendicular() == Vector(-5, -3)
        assert v.perpendicular(clockwise=False) == Vector(-5, -3)
        assert v.perpendicular(clockwise=True) == Vector(5, 3)

    def test_norm(self):
        assert Vector(0, 4).norm() == 4
        assert Vector(-2, 0).norm() == 2
        assert Vector(3, -2).norm() == pytest.approx(3.605551)

    def test_unit(self):
        assert Vector(0, 10).unit() == Vector(0, 1)
        assert Vector(3, 0).unit() == Vector(1, 0)
        assert Vector(453, -453).unit() == pytest.approx(Vector(0.707107, -0.707107))

    def test_dot(self):
        assert Vector(2, -3).dot(Vector(-4, 5)) == 2 * -4 + -3 * 5

    @staticmethod
    def assert_vectors_are_parallel(v1, v2):
        # vectors are parallel when their cross product is the zero vector
        assert v1.x * v2.y == pytest.approx(v1.y * v2.x)

    def test_projection(self):
        v1 = Vector(5, 2)

        # vector projection onto its perpendicular is (0,0) by definition
        assert v1.projection(v1.perpendicular(clockwise=False)) == Vector(0, 0)
        assert v1.projection(v1.perpendicular(clockwise=True)) == Vector(0, 0)

        assert v1.projection(Vector(0, 1)) == Vector(0, 2)
        assert v1.projection(Vector(0, -1)) == Vector(0, 2)

        assert v1.projection(Vector(1, 0)) == Vector(5, 0)
        assert v1.projection(Vector(-1, 0)) == Vector(5, 0)

        v2 = Vector(2, 3)
        p = v1.projection(v2)
        assert p == pytest.approx(Vector(2.461538, 3.692308))
        self.assert_vectors_are_parallel(v2, p)

        v2 = Vector(3, -4)
        p = v1.projection(v2)
        assert p == pytest.approx(Vector(0.84, -1.12))
        self.assert_vectors_are_parallel(v2, p)


def test_empty_rect():
    assert Rect(x=1, y=2, w=3, h=0).empty()
    assert Rect(x=1, y=2, w=0, h=3).empty()

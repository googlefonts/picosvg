from typing import NamedTuple

class Point(NamedTuple):
    x: int = 0
    y: int = 0


class Rect(NamedTuple):
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0

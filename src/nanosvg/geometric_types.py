import dataclasses


@dataclasses.dataclass(frozen=True)
class Point:
    x: int = 0
    y: int = 0


@dataclasses.dataclass(frozen=True)
class Rect:
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0

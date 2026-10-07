"""Generalization splits. Random splits leak workflow templates between
train and test and over-state accuracy; every headline number should come
from a leave-one-X-out split instead."""

from __future__ import annotations

AXES = ("family", "lang", "brand", "channel")


def leave_one_out(convs: list[dict], axis: str, value: str) -> tuple[list[dict], list[dict]]:
    if axis not in AXES:
        raise ValueError(f"axis must be one of {AXES}")
    train = [c for c in convs if c[axis] != value]
    test = [c for c in convs if c[axis] == value]
    return train, test


def values(convs: list[dict], axis: str) -> list[str]:
    return sorted({c[axis] for c in convs})

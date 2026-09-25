"""Utilities for working with enums."""

from __future__ import annotations

import dataclasses

import typing_extensions as T

if T.TYPE_CHECKING:
    import enum

    from _typeshed import DataclassInstance


def to_dataclass(
    cls: type[enum.Enum],
    dtype: type,
    name: str | None = None,
) -> type[DataclassInstance]:
    """Create a dataclass from an enum.

    One field is created for each enumeration member
    (names are converted to lowercase).

    Args:
        cls: Reference enumeration class.
        dtype: Type of the created fields.
        name: Name of the created dataclass (default `cls.__name__`).

    Returns:
        Dataclass type (created with `dataclasses.make_dataclass`).
    """
    if name is None:
        name = cls.__name__

    return dataclasses.make_dataclass(
        name,
        [(member.name.lower(), dtype) for member in cls],
    )

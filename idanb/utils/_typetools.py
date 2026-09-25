from __future__ import annotations

from collections.abc import (
    Mapping,
    Sequence,
    Set as AbstractSet,
)

import typing_extensions as T


class copy_annotations_from[**Params, Result]:  # noqa: N801
    """Decorator to copy type annotations from another function/method."""

    @T.overload
    def __init__[Self](
        self,
        *,
        method: T.Callable[T.Concatenate[Self, Params], Result],
    ) -> None:
        """Copy type annotations from another method.

        The first pamameter of method is omitted from the copied signature
        (meaning the `self` parameter is not copied).
        """

    @T.overload
    def __init__(self, function: T.Callable[Params, Result]) -> None:
        """Copy type annotations from another function."""

    def __init__(self, function: object = None, method: object = None) -> None:
        """Copy type annotations from another function or method.

        If `method` is specified, its first pamameter is omitted from the copied
        signature (meaning the `self` parameter is not copied).
        """

    def __call__(
        self,
        function: T.Callable[..., T.Any],
    ) -> T.Callable[Params, Result]:
        """Apply the copied signature onto a function."""
        return function


def is_mapping[Key, Value](
    obj: object,
    *,
    keys: type[Key] = object,
    values: type[Value] = object,
) -> T.TypeIs[Mapping[Key, Value]]:
    """Return whether `obj` is `Mapping` from `keys` to `values`.

    >>> is_mapping({1: 1, 2: 2}, keys=int, values=int)
    True
    >>> is_mapping({1: 1, 2: "2"}, keys=int, values=int)
    False
    >>> is_mapping({1: 1, 2: "2"}, keys=int)
    True
    >>> is_mapping({}, keys=str, values=bool)
    True

    """
    if not isinstance(obj, Mapping):
        return False

    # Otherwise Pyright complains about unknown variables.
    obj = T.cast("Mapping[T.Any, object]", obj)

    # Don't check contents if we don't have to.
    if keys is object and values is object:
        return True

    return all(
        isinstance(key, keys) and isinstance(value, values)
        for key, value in obj.items()
    )


def is_sequence[Elem](
    obj: object,
    /,
    *,
    elems: type[Elem] = object,
) -> T.TypeIs[Sequence[Elem]]:
    """Return whether `obj` is a `Sequence` of `elems`.

    >>> is_sequence([1, 2], elems=int)
    True
    >>> is_sequence([1, "2"], elems=int)
    False
    >>> is_sequence([1, "2"])
    True
    >>> is_sequence([], elems=str)
    True

    """
    if not isinstance(obj, Sequence):
        return False

    # Don't check contents if we don't have to.
    if elems is object:
        return True

    return all(isinstance(elem, elems) for elem in obj)


def is_set[Elem](
    obj: object,
    /,
    *,
    elems: type[Elem] = object,
) -> T.TypeIs[AbstractSet[Elem]]:
    """Return whether `obj` is a `Set` of `elems`.

    >>> is_set({1, 2}, elems=int)
    True
    >>> is_set({1, "2"}, elems=int)
    False
    >>> is_set({1, "2"})
    True
    >>> is_set(set(), elems=str)
    True

    """
    if not isinstance(obj, AbstractSet):
        return False

    # Don't check contents if we don't have to.
    if elems is object:
        return True

    return all(isinstance(elem, elems) for elem in obj)

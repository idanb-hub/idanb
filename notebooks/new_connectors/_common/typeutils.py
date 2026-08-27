from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any, Concatenate


def copy_argtypes[**P, R, Self](
    _: Callable[Concatenate[Any, P], object],
) -> Callable[
    [Callable[Concatenate[Self, ...], R]],
    Callable[Concatenate[Self, P], R],
]:
    """Copy argument annotations from another method.

    Preserves return and first argument (`self`) types.
    """
    return lambda f: f

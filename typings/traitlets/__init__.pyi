# ruff: noqa
# ruff: noqa: PGH004

import typing_extensions as T

import traitlets.traitlets as traitlets
from traitlets._version import __version__, version_info
from traitlets.traitlets import *  # pyright: ignore[reportAssignmentType]
from traitlets.utils.bunch import Bunch
from traitlets.utils.importstring import import_item
from traitlets.utils.decorators import signature_has_traits

__all__ = [
    "traitlets",
    "__version__",
    "version_info",
    "Bunch",
    "signature_has_traits",
    "import_item",
    "Sentinel",
]
__all__ += traitlets.__all__

Sentinel = traitlets.Sentinel

class HasTraits(traitlets.HasTraits):
    # Workaround for Pyright ignoring `__init__` annotations.
    # Already fixed upstream: https://github.com/ipython/traitlets/pull/918
    # Once new version is released, this can be removed.
    def __new__(cls, *args: T.Any, **kwargs: T.Any) -> T.Self: ...

# Define default get and set types for traits.

Getter = T.TypeVar("Getter", default=str)
Setter = T.TypeVar("Setter", default=Getter | bytes)

class Unicode(T.Generic[Getter, Setter], traitlets.Unicode[Getter, Setter]):
    # These overloads are copied from implementation.
    @T.overload
    def __init__(
        self: traitlets.Unicode[str, str | bytes],
        default_value: str | Sentinel = ...,
        allow_none: T.Literal[False] = ...,
        read_only: bool | None = ...,
        help: str | None = ...,
        config: T.Any = ...,
        **kwargs: T.Any,
    ) -> None: ...
    @T.overload
    def __init__(
        self: traitlets.Unicode[str | None, str | bytes | None],
        default_value: str | Sentinel | None = ...,
        allow_none: T.Literal[True] = ...,
        read_only: bool | None = ...,
        help: str | None = ...,
        config: T.Any = ...,
        **kwargs: T.Any,
    ) -> None: ...

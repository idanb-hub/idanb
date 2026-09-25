# ruff: noqa: F403

import typing_extensions as T

import traitlets.traitlets as traitlets  # noqa: PLR0402
from traitlets._version import __version__, version_info
from traitlets.traitlets import *  # pyright: ignore[reportAssignmentType]
from traitlets.utils.bunch import Bunch
from traitlets.utils.decorators import signature_has_traits
from traitlets.utils.importstring import import_item

__all__ = [
    "Bunch",
    "Sentinel",
    "__version__",
    "import_item",
    "signature_has_traits",
    "traitlets",
    "version_info",
]
__all__ += traitlets.__all__

# Implementation has this.
Sentinel = traitlets.Sentinel

# Define default get and set types for traits.

class Unicode[Get = str, Set = Get | bytes](traitlets.Unicode[Get, Set]):
    # These overloads are copied from implementation.
    @T.overload
    def __init__(
        self: Unicode[str, str | bytes],
        default_value: str | Sentinel = ...,
        allow_none: T.Literal[False] = ...,
        read_only: bool | None = ...,
        help: str | None = ...,
        config: T.Any = ...,
        **kwargs: T.Any,
    ) -> None: ...
    @T.overload
    def __init__(
        self: Unicode[str | None, str | bytes | None],
        default_value: str | Sentinel | None = ...,
        allow_none: T.Literal[True] = ...,
        read_only: bool | None = ...,
        help: str | None = ...,
        config: T.Any = ...,
        **kwargs: T.Any,
    ) -> None: ...

class Int[Get = int, Set = int](traitlets.Int[Get, Set]):
    @T.overload
    def __init__(
        self: Int[int, int],
        default_value: int | Sentinel = ...,
        allow_none: T.Literal[False] = ...,
        read_only: bool | None = ...,
        help: str | None = ...,
        config: T.Any | None = ...,
        **kwargs: T.Any,
    ) -> None: ...
    @T.overload
    def __init__(
        self: Int[int | None, int | None],
        default_value: int | Sentinel | None = ...,
        allow_none: T.Literal[True] = ...,
        read_only: bool | None = ...,
        help: str | None = ...,
        config: T.Any | None = ...,
        **kwargs: T.Any,
    ) -> None: ...

class Bool[Get = bool, Set = bool | int](traitlets.Bool[Get, Set]):
    @T.overload
    def __init__(
        self: Bool[bool, bool | int],
        default_value: bool | Sentinel = ...,
        allow_none: T.Literal[False] = ...,
        read_only: bool | None = ...,
        help: str | None = ...,
        config: T.Any = ...,
        **kwargs: T.Any,
    ) -> None: ...
    @T.overload
    def __init__(
        self: Bool[bool | None, bool | int | None],
        default_value: bool | Sentinel | None = ...,
        allow_none: T.Literal[True] = ...,
        read_only: bool | None = ...,
        help: str | None = ...,
        config: T.Any = ...,
        **kwargs: T.Any,
    ) -> None: ...

class Callable[
    **Params = ...,
    Result = T.Any,
    # For overload on `allow_none`.
    _NoneOrNever: (None, T.Never) = T.Never,
](
    traitlets.TraitType[
        T.Callable[Params, Result] | _NoneOrNever,
        T.Callable[Params, Result] | _NoneOrNever,
    ],
):
    @T.overload
    def __init__(
        self: Callable[..., T.Any, T.Never],
        default_value: T.Callable[..., T.Any] | Sentinel = ...,
        allow_none: T.Literal[False] = ...,
        read_only: bool | None = ...,
        help: str | None = ...,
        config: T.Any | None = ...,
        **kwargs: T.Any,
    ) -> None: ...
    @T.overload
    def __init__(
        self: Callable[..., T.Any, None],
        default_value: T.Callable[..., T.Any] | Sentinel = ...,
        allow_none: T.Literal[True] = ...,
        read_only: bool | None = ...,
        help: str | None = ...,
        config: T.Any | None = ...,
        **kwargs: T.Any,
    ) -> None: ...

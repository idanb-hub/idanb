from __future__ import annotations

import enum

import typing_extensions as T
import reacton

from idanb import utils


class Setter[Type](T.Protocol):
    @T.overload
    def __call__(self, value: Type, /) -> None:
        """Set the next state to a specific value."""

    @T.overload
    def __call__(self, updater: T.Callable[[Type], Type], /) -> None:
        """Set the next state as a function of the current state."""


class StateParams[Type](T.TypedDict, total=False):
    key: str
    eq: T.Callable[[Type, Type], bool]


@T.final
class use_state[Type]:  # noqa: N801
    """Wrapper around `reacton.use_state` that allows explicit typing.

    >>> @reacton.component
    ... def Example():
    ...     errmsg, set_errmsg = use_state[str | None](None)
    ...     T.assert_type(errmsg, str | None)
    ...     assert errmsg is None

    >>> _ = reacton.render(Example())
    """

    # NOTE: This won't be needed once we have PEP 718.

    def __new__(
        cls,
        initial: Type,
        **kwargs: T.Unpack[StateParams[Type]],
    ) -> tuple[Type, Setter[Type]]:
        return reacton.use_state(initial, **kwargs)


class StoreSetter[Store](T.Protocol):
    @T.overload
    def __call__[**Params, Type: utils.Record](
        self: StoreSetter[T.Callable[Params, Type]],
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> None:
        """Set specific fields of the next state.

        Omitted fields are set from the current state, not to their defaults.
        """

    @T.overload
    def __call__[Type: utils.Record](
        self: StoreSetter[Type],
        value: Type,
        /,
    ) -> None:
        """Set the next state to a specific value."""

    @T.overload
    def __call__[Type: utils.Record](
        self: StoreSetter[Type],
        updater: T.Callable[[Type], Type],
        /,
    ) -> None:
        """Set the next state as a function of the current state."""


class _Sentinel(enum.Enum):
    TOKEN = ()


def use_store[**Params, Type: utils.Record](
    initial: T.Callable[Params, Type],
) -> tuple[Type, StoreSetter[Type]]:
    """Like `use_state`, but with a setter overloaded for `Record` instances.

    >>> class State(utils.Record):
    ...     x: int = 0
    ...     y: int = 0
    ...     z: int = 0

    >>> @reacton.component
    ... def Example():
    ...     global set_state  # for testing purposes
    ...     state, set_state = use_store(State())
    ...     reacton.use_effect(lambda: print(state), [state])

    >>> _ = reacton.render(Example())
    State(x=0, y=0, z=0)

    >>> set_state(x=1, y=2)
    State(x=1, y=2, z=0)

    >>> set_state(lambda state: state(z=state.x + state.y))
    State(x=1, y=2, z=3)

    >>> set_state(State())
    State(x=0, y=0, z=0)

    """
    store, set_store = use_state(T.cast("Type", initial))

    def setter(
        value: Type | T.Callable[[Type], Type] | _Sentinel = _Sentinel.TOKEN,
        /,
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> None:
        if value is _Sentinel.TOKEN:
            set_store(lambda store: store(*args, **kwargs))
        elif isinstance(value, utils.Record):
            set_store(lambda _: value)
        else:
            set_store(value)

    return store, setter


def cast_setter_to_update_only[Type](
    setter: T.Callable[[Type | T.Callable[[Type], Type]], None],
) -> T.Callable[[T.Callable[[Type], Type]], None]:
    """Narrow the type of `setter` to its update overload only.

    This might help when type-checkers can't infer argument types for the
    overloaded version. At runtime, this returns `setter` unchanged.

    ```python
    n, set_n = reacton.use_state(0)
    reveal_type(set_n)  # (int | (int) -> int) -> None
    set_n = cast_setter_to_update_only(set_n)
    reveal_type(set_n)  # ((int) -> int) -> None
    ```

    Maybe once Pyright fixes #11603, this won't be necessary.
    See: https://github.com/microsoft/pyright/issues/11603
    """
    return setter

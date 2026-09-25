from __future__ import annotations

import typing_extensions as T
import reacton

if T.TYPE_CHECKING:
    from .state import StateParams


def use_previous[Value](value: Value) -> Value:
    ref = reacton.use_ref(value)

    def assign() -> None:
        ref.current = value

    reacton.use_effect(assign, [value])
    return ref.current


def use_state_from[Value](
    value: Value,
    on_change: T.Callable[[Value], None] | None = None,
    **kwargs: T.Unpack[StateParams[Value]],
) -> tuple[Value, T.Callable[[Value | T.Callable[[Value], Value]], None]]:
    local_value, set_local_value = reacton.use_state(value, **kwargs)

    def update() -> None:
        set_local_value(value)
        # Update returned local value immediately.
        nonlocal local_value
        local_value = value

    reacton.use_memo(update, [value])

    def on_value() -> None:
        if on_change is not None:
            on_change(local_value)

    reacton.use_effect(on_value, [local_value])

    return local_value, set_local_value

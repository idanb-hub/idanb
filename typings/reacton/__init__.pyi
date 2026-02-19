import ipywidgets
import typing_extensions as T

import reacton.core as _core

@T.overload
def component[Widget: ipywidgets.Widget](
    obj: type[Widget],
) -> _core.Element[Widget]: ...
@T.overload
def component[**Params](
    obj: T.Callable[Params, None],
) -> T.Callable[Params, _core.Element[_core.Component]]: ...
@T.overload
def component[**Params, Widget: ipywidgets.Widget](
    obj: T.Callable[Params, _core.Element[Widget]],
) -> T.Callable[Params, _core.Element[Widget]]: ...
def render[Widget, Container](
    element: _core.Element[Widget],
    container: Container | None = None,
    children_trait: str = "children",
    handle_error: bool = True,
    initial_state: dict[str, T.Any] | None = None,
) -> tuple[Container, _core._RenderContext]: ...
def use_state[Type](
    initial: Type,
    key: str | None = None,
    eq: T.Callable[[T.Any, T.Any], bool] | None = None,
) -> tuple[
    Type,
    T.Callable[
        [Type | T.Callable[[Type], Type]],
        None,
    ],
]: ...
def use_effect(
    effect: _core.EffectCallable,
    dependencies: list[T.Any] | None = None,
) -> None: ...
def use_memo[Type](
    f: T.Callable[[], Type],
    dependencies: list[T.Any] | None = None,
    debug_name: str | None = None,
) -> Type: ...
def use_context[Type](user_context: _core.UserContext[Type]) -> Type: ...
def use_reducer[State, Action](
    reduce: T.Callable[[State, Action], State],
    initial_state: State,
) -> tuple[State, T.Callable[[Action], None]]: ...
def use_ref[Type](initial_value: Type) -> _core.Ref[Type]: ...
def provide_context[Type](
    user_context: _core.UserContext[Type],
    obj: Type,
) -> None: ...
def create_context[Type](
    default_value: Type,
    name: str | None = None,
) -> _core.UserContext[Type]: ...
def get_widget[Widget](el: _core.Element[Widget]) -> Widget: ...

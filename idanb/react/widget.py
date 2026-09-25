from __future__ import annotations

import functools
import logging

import typing_extensions as T
import reacton
import traitlets

# Because `traitlets.Sentinel` dees not work for `isinstance` checks.
from traitlets.traitlets import Sentinel

from .state import Setter, use_state

if T.TYPE_CHECKING:
    from reacton.core import Element


_logger = logging.getLogger(__name__)


def use_widget[Widget](element: Element[Widget]) -> Widget | None:
    widget, set_widget = use_state[Widget | None](None)

    def on_element() -> None:
        try:
            widget = reacton.get_widget(element)
        except KeyError:
            _logger.exception("Can't get widget from element")
        else:
            set_widget(widget)

    reacton.use_effect(on_element, [element])

    return widget


def get_trait_default[Widget: traitlets.HasTraits, Value](
    element: Element[Widget],
    trait: traitlets.TraitType[Value, T.Any],
    default: Value | Sentinel = traitlets.Undefined,
) -> Value:
    try:
        return T.cast("Value", element.kwargs[trait.name])
    except KeyError:
        pass

    value = T.cast("Value | Sentinel", trait.default())
    if not isinstance(value, Sentinel):
        return value

    if not isinstance(default, Sentinel):
        return default

    errmsg = "can't get trait default value"
    raise ValueError(errmsg)


def use_widget_state[Widget: traitlets.HasTraits, Value](
    element: Element[Widget],
    trait: traitlets.TraitType[Value, T.Any],
    *,
    default: Value | Sentinel = traitlets.Undefined,
) -> tuple[Value, Setter[Value]]:
    if trait.name is None:
        errmsg = "trait does not have name set"
        raise ValueError(errmsg)

    widget = use_widget(element)
    trait_name = trait.name

    def get_trait_value(widget: Widget) -> Value:
        return trait.__get__(widget, type(widget))

    if widget is None:
        value = get_trait_default(element, trait, default)
    else:
        value = get_trait_value(widget)

    value, set_value = use_state(value)

    def on_widget() -> T.Callable[[], None] | None:
        if widget is None:
            return None

        set_value(get_trait_value(widget))

        def on_change(_change: object, widget: Widget = widget) -> None:
            set_value(get_trait_value(widget))

        widget.observe(on_change, trait_name)
        return functools.partial(widget.unobserve, on_change, trait_name)

    reacton.use_effect(on_widget, [widget])

    def set_trait_value(new_value: Value | T.Callable[[Value], Value]) -> None:
        if widget is None:
            errmsg = "can't set trait before widget is created"
            raise RuntimeError(errmsg)

        if callable(new_value):
            new_value = new_value(value)

        trait.__set__(widget, new_value)

    return value, set_trait_value

from __future__ import annotations

import uuid

import typing_extensions as T

from idanb import react, widgets

if T.TYPE_CHECKING:
    from reacton.core import Element


def _css(rules: T.Mapping[str, str | T.Mapping[str, str]], scope: str) -> str:
    content = "".join(
        (
            f"{key}:{value};"
            if isinstance(value, str)
            else f"{key}{_css(value, '')}"
        )
        for key, value in rules.items()
    )
    return "%s{%s}" % (scope, content)  # noqa: UP031


@react.component
def LocalStyle(  # noqa: N802
    rules: T.Mapping[str, str | T.Mapping[str, str]] | None = None,
    /,
    **rules_: str | T.Mapping[str, str],
) -> Element[widgets.HTML]:
    rules = dict(rules) if rules else {}
    rules.update(rules_)

    css_class = react.use_memo(lambda: f"_{uuid.uuid4().hex}")
    css = _css(rules, f"*:has(> .{css_class})")

    elem = widgets.HTML.element(f"<style>{css}</style>")

    def init() -> None:
        widget = react.get_widget(elem)
        widget.add_class(css_class)

    react.use_effect(init)
    return elem


# %run style.ipy

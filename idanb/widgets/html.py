from __future__ import annotations

from pathlib import Path

import typing_extensions as T
import anywidget
import traitlets

if T.TYPE_CHECKING:
    from reacton.core import Element


class HTML(anywidget.AnyWidget):
    _esm: str | Path = Path(__file__).with_suffix(".js")

    html: traitlets.Unicode = traitlets.Unicode().tag(sync=True)

    def __init__(self, html: str = "", **kwargs: object) -> None:
        super().__init__(html=html, **kwargs)

    @T.override
    @classmethod
    def element(
        cls,
        html: str | None = None,
        **kwargs: object,
    ) -> Element[T.Self]:
        if html is not None:
            kwargs["html"] = html
        return super().element(**kwargs)

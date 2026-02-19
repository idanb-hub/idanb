import typing_extensions as T
from reacton.core import Element

import anywidget.widget
from anywidget._version import __version__

__all__ = ["AnyWidget", "__version__"]

class AnyWidget(anywidget.widget.AnyWidget):
    # Implementation has incorrect annotations.
    def __init_subclass__(cls, **kwargs: object) -> None: ...

    # This comes from `reacton`.
    # https://github.com/widgetti/reacton/blob/v1.9.1/reacton/core.py#L131
    @classmethod
    def element(cls, **kwargs: T.Any) -> Element[T.Any]: ...

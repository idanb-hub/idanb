from __future__ import annotations

import typing_extensions as T
from IPython.display import display

from idanb import widgets

if T.TYPE_CHECKING:
    pass


def init() -> widgets.RPC:
    global rpc  # noqa: PLW0603

    if rpc is None:
        rpc = widgets.RPC()

    if not rpc._view_count:  # noqa: SLF001
        display(rpc)

    return rpc


rpc: widgets.RPC | None = None


def exec(expr: str, /, **vars: object) -> None:  # noqa: A001
    """Evaluate `expr` as a JavaScript expression on the frontend.

    Keyword arguments be used in `expr`. Scalar values and functions work,
    complex objects might not.
    """
    init().eval(expr, **vars)

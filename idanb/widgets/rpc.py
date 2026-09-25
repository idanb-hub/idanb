from __future__ import annotations

import logging
import weakref
from pathlib import Path

import typing_extensions as T
import anywidget

_logger = logging.getLogger(__name__)


class RPC(anywidget.AnyWidget):
    _esm: str | Path = Path(__file__).with_suffix(".js")

    _funcs: weakref.WeakValueDictionary[int, T.Callable[..., object]]

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._funcs = weakref.WeakValueDictionary()
        super().__init__(*args, **kwargs)
        self.on_msg(type(self).on_custom_msg)

    def _pack_variable(self, value: object) -> object:
        if callable(value):
            func_id = id(value)
            self._funcs[func_id] = value
            t = "function"
            v = func_id
        else:
            t = "object"
            v = value

        return {"type": t, "value": v}

    def eval(self, expr: str, **vars: object) -> None:
        vars_pack = {
            name: self._pack_variable(value) for name, value in vars.items()
        }
        self.send({"expr": expr, "vars": vars_pack})

    def on_custom_msg(self, content: object, buffers: list[memoryview]) -> None:
        del buffers

        match content:
            case {"func": int(func_id), "params": list(params)}:
                func = self._funcs[func_id]
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug(
                        "Calling function: %s.%s(%s)",
                        func.__module__,
                        func.__qualname__,
                        ", ".join(map(repr, params)),
                    )
                _ = func(*params)
            case _:
                pass


# %run rpc.ipy

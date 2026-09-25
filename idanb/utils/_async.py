from __future__ import annotations

import asyncio
import contextvars

import typing_extensions as T


def forget_task(coro: T.Coroutine[T.Any, T.Any, T.Any]) -> None:
    """Run a coroutine in the background.

    Like `asyncio.create_task`, but prevents the task from being garbage
    collected before it's done.
    """
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


_background_tasks: set[asyncio.Task[object]] = set()


class ContextProxy[Target]:
    """Transparently wraps an object in a `contextvars.ContextVar`.

    Attribute access is delegated to the wrapped object.
    Methods of `ContextVar` are accessible as static methods.

    ```py
    out = ContextProxy(sys.stdout)
    token = ContextProxy.set(out, sys.stderr)
    out.write("this goes to stderr")
    ContextProxy.reset(token)
    out.write("this goes to stdout")
    ```

    Forwarding of dunder methods is not implemented.
    """

    _target: contextvars.ContextVar[Target]

    if T.TYPE_CHECKING:
        # This makes `ContextProxy` appear transparent to type-checkers.
        def __new__(cls, target: Target) -> Target: ...

    def __init__(self, target: Target) -> None:
        if isinstance(target, ContextProxy):
            errmsg = f"target {target!r} is already wrapped in {ContextProxy.__name__}"
            raise TypeError(errmsg) from None
        self._target = contextvars.ContextVar("_target", default=target)

    @staticmethod
    def target[Target_](
        instance: ContextProxy[Target_],
    ) -> contextvars.ContextVar[Target_]:
        return object.__getattribute__(instance, "_target")

    @staticmethod
    def get[Target_](
        instance: ContextProxy[Target_],
    ) -> Target_:
        return __class__.target(instance).get()

    @staticmethod
    def set[Target_](
        instance: ContextProxy[Target_],
        value: Target_,
    ) -> contextvars.Token[Target_]:
        return __class__.target(instance).set(value)

    @staticmethod
    def reset[Target_](
        instance: ContextProxy[Target_],
        token: contextvars.Token[Target_],
    ) -> None:
        return __class__.target(instance).reset(token)

    @T.override
    def __getattribute__(self, attr: str) -> T.Any:
        return getattr(type(self).get(self), attr)

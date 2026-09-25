from __future__ import annotations

import asyncio
import enum

import typing_extensions as T

from .globals import Global, create_global, use_global
from .state import use_state


class _NoResultEnum(enum.Enum):
    NO_RESULT = ()


type NoResult = T.Literal[_NoResultEnum.NO_RESULT]
NO_RESULT: NoResult = _NoResultEnum.NO_RESULT


class TaskStatus:
    class NotCalled:
        pass

    class Pending:
        pass

    class Cancelled:
        pass

    class Exception(T.NamedTuple):  # noqa: A001
        exception: BaseException

    class Result[Type](T.NamedTuple):
        result: Type


class Task[**Params, Result](TaskStatus):
    _func: T.Callable[Params, T.Awaitable[Result]]
    _future: asyncio.Future[Result] | None
    _set_future: T.Callable[[asyncio.Future[Result]], None] | None

    def __init__(
        self,
        func: T.Callable[Params, T.Awaitable[Result]],
        future: asyncio.Future[Result] | None = None,
        set_future: T.Callable[[asyncio.Future[Result]], None] | None = None,
    ) -> None:
        self._func = func
        self._future = future
        self._set_future = set_future

    def __call__(
        self,
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> T.Awaitable[Result]:
        self.cancel()
        result = self._func(*args, **kwargs)
        future = asyncio.ensure_future(result)

        if self._set_future is not None:
            self._set_future(future)
            future.add_done_callback(self._set_future)

        self._future = future
        return future

    def start(self, *args: Params.args, **kwargs: Params.kwargs) -> None:
        _ = self(*args, **kwargs)

    def cancel(self) -> None:
        if self._future is None:
            return

        _ = self._future.cancel()

    @property
    def not_called(self) -> bool:
        return self._future is None

    @property
    def pending(self) -> bool:
        return self._future is not None and not self._future.done()

    @property
    def cancelled(self) -> bool:
        return self._future is not None and self._future.cancelled()

    @property
    def exception(self) -> BaseException | None:
        f = self._future

        if f is None or not f.done() or f.cancelled():
            return None

        return f.exception()

    NO_RESULT: T.Final = NO_RESULT

    @property
    def result(self) -> Result | NoResult:
        f = self._future

        if (
            f is None
            or not f.done()
            or f.cancelled()
            or f.exception() is not None
        ):
            return self.NO_RESULT

        return f.result()

    @property
    def status(
        self,
    ) -> T.Union[  # noqa: UP007
        Task.NotCalled,
        Task.Cancelled,
        Task.Pending,
        Task.Exception,
        Task.Result[Result],
    ]:
        if self.not_called:
            return self.NotCalled()
        if self.cancelled:
            return self.Cancelled()
        if self.pending:
            return self.Pending()
        if self.exception is not None:
            return self.Exception(self.exception)
        if self.result is not self.NO_RESULT:
            return self.Result(self.result)

        errmsg = "unreachable"
        raise AssertionError(errmsg)


class GlobalTask[**Params, Result]:
    _func: T.Callable[Params, T.Awaitable[Result]]
    _glob: Global[asyncio.Future[Result] | None]

    def __init__(
        self,
        func: T.Callable[Params, T.Awaitable[Result]],
    ) -> None:
        self._func = func
        self._glob = create_global(None, eq=lambda _l, _r: False)

    def peek(self) -> Task[Params, Result]:
        future = self._glob.peek()
        return Task(self._func, future)

    def use(self) -> Task[Params, Result]:
        future, set_future = use_global(self._glob)
        return Task(self._func, future, set_future)


def task[Result, **Params]() -> T.Callable[
    [T.Callable[Params, T.Awaitable[Result]]],
    GlobalTask[Params, Result],
]:
    def decorator(
        func: T.Callable[Params, T.Awaitable[Result]],
    ) -> GlobalTask[Params, Result]:
        return GlobalTask(func)

    return decorator


@T.overload
def use_task[Result, **Params]() -> T.Callable[
    [T.Callable[Params, T.Awaitable[Result]]],
    Task[Params, Result],
]: ...


@T.overload
def use_task[Result, **Params](
    task: GlobalTask[Params, Result],
) -> Task[Params, Result]: ...


def use_task[Result, **Params](
    task: GlobalTask[Params, Result] | None = None,
) -> (
    Task[Params, Result]
    | T.Callable[
        [T.Callable[Params, T.Awaitable[Result]]],
        Task[Params, Result],
    ]
):
    if task is not None:
        return task.use()

    def decorator(
        func: T.Callable[Params, T.Awaitable[Result]],
    ) -> Task[Params, Result]:
        future, set_future = use_state[asyncio.Future[Result] | None](
            None,
            # Always update, even when the new value equals the current one.
            eq=lambda _l, _r: False,
        )

        return Task(func, future, set_future)

    return decorator

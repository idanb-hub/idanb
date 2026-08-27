from __future__ import annotations

import collections.abc
import contextlib
import typing

if typing.TYPE_CHECKING:
    import types
    from collections.abc import AsyncIterator, Awaitable, Callable, Generator


class AwaitableContextManager[Enter, Exit: bool | None, Result](
    contextlib.AbstractAsyncContextManager[Enter, Exit],
    collections.abc.Awaitable[Result],
):
    _inner: contextlib.AbstractAsyncContextManager[Enter, Exit]
    _collect: Callable[[Enter], Awaitable[Result]]

    def __init__(
        self,
        inner: contextlib.AbstractAsyncContextManager[Enter, Exit],
        collect: Callable[[Enter], Awaitable[Result]],
    ) -> None:
        self._inner = inner
        self._collect = collect

    @typing.override
    async def __aenter__(self) -> Enter:
        return await self._inner.__aenter__()

    @typing.override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
        /,
    ) -> Exit:
        return await self._inner.__aexit__(exc_type, exc_value, traceback)

    @typing.override
    def __await__(self) -> Generator[typing.Any, None, Result]:
        async def awaitable() -> Result:
            async with self as ctx:
                return await self._collect(ctx)

        return awaitable().__await__()


class queryfactory[Result]:  # noqa: N801
    """Decorator factory for creating query context manager factories.

    Works like `contextlib.asynccontextmanager`, except the created context
    managers are also awaitable. Awaiting them is equivalent to awaiting
    `collect` invoked on their managed context. Typically, `collect` will
    be a method of the managed context class.

    If the managed context is awaitable itself, `collect` can be omitted,
    in which case awaiting the context manager is equivalent to awaiting its
    context.

    Example:
    ```py
    class Query:  # the managed context class
        async def result(): ...

    class Connector:
        @queryfactory(Query.result)
        async def query():
            # See `contextlib.asynccontextmanager` for what to put here.
            yield Query(...)

    connector = Connector()
    # Context manager works same as with `contextlib.asynccontextmanager`.
    async with connector.query() as query:
        result = await query.result()
    # But it can also be awaited directly. Next line is equivalent to ^.
    result = await connector.query()
    ```
    """

    @typing.overload
    def __new__[Enter: Awaitable[typing.Any], **Params](
        cls,
    ) -> Callable[
        [Callable[Params, AsyncIterator[Enter]]],
        Callable[
            Params,
            AwaitableContextManager[Enter, bool | None, Result],
        ],
    ]: ...

    @typing.overload
    def __new__[Enter, **Params](
        cls,
        collect: Callable[[Enter], Awaitable[Result]],
    ) -> Callable[
        [Callable[Params, AsyncIterator[Enter]]],
        Callable[Params, AwaitableContextManager[Enter, bool | None, Result]],
    ]: ...

    def __new__[Enter, **Params](
        cls,
        collect: Callable[[Enter], Awaitable[Result]] | None = None,
    ) -> Callable[
        [Callable[Params, AsyncIterator[Enter]]],
        Callable[Params, AwaitableContextManager[Enter, bool | None, Result]],
    ]:
        if collect is None:
            collect = lambda result: typing.cast("Awaitable[Result]", result)  # noqa: E731

        def decorator(
            func: Callable[Params, AsyncIterator[Enter]],
        ) -> Callable[
            Params,
            AwaitableContextManager[Enter, bool | None, Result],
        ]:
            ctxmgr = contextlib.asynccontextmanager(func)

            def decorated(
                *args: Params.args,
                **kwargs: Params.kwargs,
            ) -> AwaitableContextManager[Enter, bool | None, Result]:
                ctx = ctxmgr(*args, **kwargs)
                return AwaitableContextManager(ctx, collect)

            return decorated

        return decorator

from __future__ import annotations

import abc
import functools
import inspect

import typing_extensions as T

from ._typetools import copy_annotations_from


def decorator[Func, **Params, Result](
    func: T.Callable[T.Concatenate[Func, Params], Result],
) -> T.Callable[Params, T.Callable[[Func], Result]]:
    """Create a parameterized decorator from a higher-order function.

    >>> @decorator
    ... def skip_args(f, count):
    ...     return lambda *args: f(*args[count:])

    >>> @skip_args(1)
    ... def bar(*args):
    ...     print(*args)
    >>> bar(1, 2)
    2

    >>> @skip_args(count=1)
    ... def baz(*args):
    ...     print(*args)
    >>> baz(1, 2)
    2

    """

    @functools.wraps(func)
    def decorated(
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> T.Callable[[Func], Result]:
        return lambda f, /: func(f, *args, **kwargs)

    return decorated


def universaldecorator[**Params, Result](
    genfunc: T.Callable[
        T.Concatenate[T.Callable[Params, None], Params],
        T.Generator[None, Result, Result],
    ],
) -> UniversalDecorator[Params, Result]:
    """Create a universal decorator from a generator function.

    Functions decorated with the created decorator forward their arguments
    to this generator function, along with a setter function that can be used
    to change these arguments before they are passed to the decorated function.

    The generator function must yield `None` exactly once to pass control to
    the decorated function and receive its result.

    >>> @universaldecorator
    ... def log(set_args, *args, **kwargs):
    ...     # Do something with the arguments.
    ...     print(f"args={args} kwargs={kwargs}")
    ...     set_args(*args, **kwargs)
    ...     try:
    ...         # Call the decorated function and get what its final result.
    ...         result = yield
    ...     except Exception as e:
    ...         # The decorated function raised an exception before completing.
    ...         print(f"exception={e}")
    ...         # Re-raise it or return a value instead.
    ...         return None
    ...     else:
    ...         # Do something with the final result and return.
    ...         print(f"result={result}")
    ...         return None

    Regular (non-async, non-generator) function.

    >>> @log
    ... def div(a, b):
    ...     return a / b

    >>> div(1, 2)
    args=(1, 2) kwargs={}
    result=0.5

    >>> div(a=1, b=0)
    args=() kwargs={'a': 1, 'b': 0}
    exception=division by zero

    Generator function.

    >>> @log
    ... def count(elems):
    ...     for i, elem in enumerate(elems, start=1):
    ...         yield elem
    ...     return i

    >>> for x in count("abc"):
    ...     print(x)
    args=('abc',) kwargs={}
    a
    b
    c
    result=3

    Async function.

    >>> @log
    ... async def identity(x):
    ...    return x

    >>> await identity(1)
    args=(1,) kwargs={}
    result=1

    Async generator function.

    >>> @log
    ... async def asyncrange(stop):
    ...     for n in range(stop):
    ...         yield n

    >>> async for n in asyncrange(3):
    ...     print(n)
    args=(3,) kwargs={}
    0
    1
    2
    result=None

    """
    return _UniversalDecoratorFromGeneratorFunction(genfunc)


class UniversalDecorator[**Params, Result](abc.ABC):
    """Decorator that supports all functions (async and/or generators).

    This relies `inspect.is*function()` to detect what kind of function is
    being decorated, which takes only the function's definition into account.
    To decorate callable objects or plain functions returning
    generators/awaitables, use the appropriate `.decorate_*()` method directly.
    """

    @abc.abstractmethod
    def decorate_sync(
        self,
        func: T.Callable[Params, Result],
    ) -> T.Callable[Params, Result]: ...

    @abc.abstractmethod
    def decorate_gen[Yield, Send](
        self,
        func: T.Callable[Params, T.Generator[Yield, Send, Result]],
    ) -> T.Callable[Params, T.Generator[Yield, Send, Result]]: ...

    @abc.abstractmethod
    def decorate_async(
        self,
        func: T.Callable[Params, T.Awaitable[Result]],
    ) -> T.Callable[Params, T.Awaitable[Result]]: ...

    @abc.abstractmethod
    def decorate_asyncgen[Yield, Send](
        self,
        func: T.Callable[Params, T.AsyncGenerator[Yield, Send]],
    ) -> T.Callable[Params, T.AsyncGenerator[Yield, Send]]: ...

    # The order of overloads matters! First applicable gets used.

    @T.overload
    @copy_annotations_from(decorate_asyncgen)
    def __call__(self, func: object) -> object: ...

    @T.overload
    @copy_annotations_from(decorate_gen)
    def __call__(self, func: object) -> object: ...

    @T.overload
    @copy_annotations_from(decorate_async)
    def __call__(self, func: object) -> object: ...

    @T.overload
    @copy_annotations_from(decorate_sync)
    def __call__(self, func: object) -> object: ...

    def __call__(
        self,
        func: T.Callable[Params, Result],
    ) -> T.Callable[Params, T.Any]:
        if inspect.isasyncgenfunction(func):
            return self.decorate_asyncgen(func)
        if inspect.iscoroutinefunction(func):
            return self.decorate_async(func)
        if inspect.isgeneratorfunction(func):
            return self.decorate_gen(func)

        return self.decorate_sync(func)


class UniversalDecoratorBase[**Params, Result, *Context](
    UniversalDecorator[Params, Result],
):
    """Base class for custom `UniversalDecorator` implementations.

    Concrete decorators are implemented by overriding any of the `_pre`,
    `_post`, `_except`, and `_finally` methods. By default, they do nothing.
    """

    def _pre(
        self,
        set_args: T.Callable[Params, None],
        /,
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> tuple[*Context] | None:
        """Alter the arguments before they are passed to the decorated function.

        Args:
            set_args: Function that sets arguments for the decorated function.
            args: Positional arguments for the decorated function.
            kwargs: Keyword arguments for the decorated function.

        Returns:
            Context which is passed as additional arguments to `_post`,
            `_except`, and `_finally` (defaults to `()`).

        Raises:
            StopIteration: Return a value immediately instead of calling the
                decorated function.
        """
        set_args(*args, **kwargs)

    def _post(self, result: Result, *context: *Context) -> Result:
        """Intercept the result returned by the decorated function.

        Args:
            result: Result returned by the decorated function.
            context: Context returned by `_pre`.

        Returns:
            Result to return to the caller.
        """
        del context
        return result

    def _except(self, exc: BaseException, *context: *Context) -> Result:
        """Handle an exception raised by the decorated function.

        Args:
            exc: Exception raised by the decorated function.
            context: Context returned by `_pre`.

        Returns:
            Result to return to the caller (and suppress the exception).

        Raises:
            BaseException: May be `exc` or a completely different exception.
        """
        del context
        raise exc

    def _finally(self, *context: *Context) -> None:
        """Clean up after the decorated function either returned or raised.

        The respective `_post` or `_except` method is called first, similar to
        a `finally` clause in a `try` statement.

        Args:
            context: Context returned by `_pre`.
        """
        del context

    def __pre(
        self,
        set_args: T.Callable[Params, None],
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> tuple[*Context]:
        context = self._pre(set_args, *args, **kwargs)

        if context is None:
            context = T.cast("tuple[*Context]", ())

        return context

    @T.override
    def decorate_sync(
        self,
        func: T.Callable[Params, Result],
    ) -> T.Callable[Params, Result]:

        @functools.wraps(func)
        def decorated(*args: Params.args, **kwargs: Params.kwargs) -> Result:

            def set_args(*args2: Params.args, **kwargs2: Params.kwargs) -> None:
                nonlocal args, kwargs
                args, kwargs = args2, kwargs2

            try:
                context = self.__pre(set_args, *args, **kwargs)
            except StopIteration as e:
                return e.value

            try:
                result = func(*args, **kwargs)
            except BaseException as e:  # noqa: BLE001
                return self._except(e, *context)
            else:
                return self._post(result, *context)
            finally:
                self._finally(*context)

        return decorated

    @T.override
    def decorate_gen[Yield, Send](
        self,
        func: T.Callable[Params, T.Generator[Yield, Send, Result]],
    ) -> T.Callable[Params, T.Generator[Yield, Send, Result]]:

        @functools.wraps(func)
        def decorated(
            *args: Params.args, **kwargs: Params.kwargs
        ) -> T.Generator[Yield, Send, Result]:

            def set_args(*args2: Params.args, **kwargs2: Params.kwargs) -> None:
                nonlocal args, kwargs
                args, kwargs = args2, kwargs2

            try:
                context = self.__pre(set_args, *args, **kwargs)
            except StopIteration as e:
                return e.value

            try:
                result = yield from func(*args, **kwargs)
            except BaseException as e:  # noqa: BLE001
                return self._except(e, *context)
            else:
                return self._post(result, *context)
            finally:
                self._finally(*context)

        return decorated

    @T.override
    def decorate_async(
        self,
        func: T.Callable[Params, T.Awaitable[Result]],
    ) -> T.Callable[Params, T.Awaitable[Result]]:

        @functools.wraps(func)
        async def decorated(
            *args: Params.args,
            **kwargs: Params.kwargs,
        ) -> Result:

            def set_args(*args2: Params.args, **kwargs2: Params.kwargs) -> None:
                nonlocal args, kwargs
                args, kwargs = args2, kwargs2

            try:
                context = self.__pre(set_args, *args, **kwargs)
            except StopIteration as e:
                return e.value

            try:
                result = await func(*args, **kwargs)
            except BaseException as e:  # noqa: BLE001
                return self._except(e, *context)
            else:
                return self._post(result, *context)
            finally:
                self._finally(*context)

        return decorated

    @T.override
    def decorate_asyncgen[Yield, Send](  # noqa: C901, PLR0915
        self,
        func: T.Callable[Params, T.AsyncGenerator[Yield, Send]],
    ) -> T.Callable[Params, T.AsyncGenerator[Yield, Send]]:

        @functools.wraps(func)
        async def decorated(  # noqa: C901, PLR0912, PLR0915
            *args: Params.args,
            **kwargs: Params.kwargs,
        ) -> T.AsyncGenerator[Yield, Send]:

            def set_args(*args2: Params.args, **kwargs2: Params.kwargs) -> None:
                nonlocal args, kwargs
                args, kwargs = args2, kwargs2

            try:
                context = self.__pre(set_args, *args, **kwargs)
            except StopIteration as e:
                raise StopAsyncIteration(e.value) from e

            try:
                # Async generators don't support `yield from` in Python < 3.16.
                # See:
                #   https://peps.python.org/pep-0828/
                #
                # The following code was taken from the `yield from` PEP and
                # adapted for async generators.
                # See:
                #   https://peps.python.org/pep-0380/#formal-semantics

                EXPR = func(*args, **kwargs)  # noqa: N806
                _i = EXPR
                try:
                    _y = await anext(_i)
                except StopAsyncIteration as _e:
                    _r = getattr(_e, "value", None)
                else:
                    while 1:
                        try:
                            _s = yield _y
                        except GeneratorExit as _e:
                            try:
                                _m = _i.aclose
                            except AttributeError:
                                pass
                            else:
                                await _m()
                            raise _e from None
                        except BaseException as _e:  # noqa: BLE001
                            _x = (type(_e), _e, _e.__traceback__)
                            try:
                                _m = _i.athrow
                            except AttributeError:
                                raise _e from None
                            else:
                                try:
                                    _y = await _m(*_x)
                                except StopAsyncIteration as _e:
                                    _r = getattr(_e, "value", None)
                                    break
                        else:
                            try:
                                if _s is None:
                                    _y = await anext(_i)
                                else:
                                    _y = await _i.asend(_s)
                            except StopAsyncIteration as _e:
                                _r = getattr(_e, "value", None)
                                break
                RESULT = _r  # noqa: N806

                # ============================================================ #

                result = T.cast("Result", RESULT)

            except BaseException as e:  # noqa: BLE001
                result = self._except(e, *context)
                # TODO: Replace with `return result` once we're on Python 3.16.
                if result is not None:
                    raise StopAsyncIteration(result) from None
            else:
                result = self._post(result, *context)
                # TODO: Replace with `return result` once we're on Python 3.16.
                if result is not None:
                    raise StopAsyncIteration(result)
            finally:
                self._finally(*context)

        return decorated


class _UniversalDecoratorFromGeneratorFunction[Result, **Params](
    UniversalDecoratorBase[Params, Result, "T.Generator[None, Result, Result]"],
):
    _genfunc: T.Callable[
        T.Concatenate[T.Callable[Params, None], Params],
        T.Generator[None, Result, Result],
    ]

    def __init__(
        self,
        genfunc: T.Callable[
            T.Concatenate[T.Callable[Params, None], Params],
            T.Generator[None, Result, Result],
        ],
    ) -> None:
        self._genfunc = genfunc

    @T.override
    def _pre(
        self,
        set_args: T.Callable[Params, None],
        /,
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> tuple[T.Generator[None, Result, Result]]:
        gen = self._genfunc(set_args, *args, **kwargs)
        try:
            value = next(gen)
            if value is not None:
                errmsg = "generator yielded not None"
                raise ValueError(errmsg)
        except StopIteration as e:
            raise StopIteration(e.value) from None

        return (gen,)

    @T.override
    def _post(
        self,
        result: Result,
        gen: T.Generator[None, Result, Result],
    ) -> Result:
        try:
            _ = gen.send(result)
        except StopIteration as e:
            return e.value

        errmsg = "generator didn't stop"
        raise RuntimeError(errmsg)

    @T.override
    def _except(
        self,
        exc: BaseException,
        gen: T.Generator[None, Result, Result],
    ) -> T.Any:
        try:
            _ = gen.throw(exc)
        except StopIteration as stop:
            # Make sure its not the exception we passed in.
            if stop is exc:
                raise stop from None
            return stop.value

        errmsg = "generator didn't stop"
        raise RuntimeError(errmsg)

    @T.override
    def _finally(self, gen: T.Generator[None, Result, Result]) -> None:
        _ = gen.close()

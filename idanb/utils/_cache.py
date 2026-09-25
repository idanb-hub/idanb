from __future__ import annotations

import contextlib
import functools
import hashlib
import inspect
import logging
import os
import pickle
import tempfile
from pathlib import Path

import typing_extensions as T

from ._decorator import universaldecorator

if T.TYPE_CHECKING:
    pass


_logger = logging.getLogger(__name__)


# Because typeshed's annotation doesn't preserve docstrings.
if T.TYPE_CHECKING:

    def cache[Func](func: Func, /) -> Func:
        """Alias for `functools.cache` that preserves function type."""
        ...

else:
    cache = functools.cache


# Because typeshed's annotation doesn't preserve docstrings.
if T.TYPE_CHECKING:

    def lru_cache[Func](
        maxsize: int | None = 128,
        *,
        typed: bool = True,
    ) -> T.Callable[[Func], Func]:
        """Alias for `functools.lru_cache` that preserves function type."""
        ...

else:
    lru_cache = functools.lru_cache


class fs_cache:  # noqa: N801
    """Persistent function cache.

    Requires both function arguments and the cached results to be pickle-able.

    >>> tempdir = tempfile.TemporaryDirectory()

    >>> @fs_cache(tempdir.name)
    ... def cache_sum(*args):
    ...     print("cold")
    ...     return sum(args)

    >>> assert cache_sum(1, 2, 3) == 6
    cold
    >>> assert cache_sum(1, 2, 3) == 6
    >>> assert cache_sum(1, 2) == 3
    cold

    Use closures to exclude arguments from being cached.

    >>> def cache_sum_ex(*args, msg):
    ...     @fs_cache(tempdir.name)
    ...     def impl(*args):
    ...         print(msg)
    ...         return sum(args)
    ...     return impl(*args)

    >>> assert cache_sum_ex(1, 2, 3, msg="cold") == 6
    cold
    >>> assert cache_sum_ex(1, 2, 3, msg="blah") == 6
    """

    cachedir: Path

    def __init__(self, cachedir: str | Path | None) -> None:
        if cachedir is None:
            cachedir = tempfile.gettempdir()
        self.cachedir = Path(cachedir)

    def _cache_key(
        self,
        func: T.Callable[..., object],
        *args: object,
        **kwargs: object,
    ) -> str:
        # Normalize args and kwargs against function signature.
        signature = inspect.signature(func)
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()

        # Include function "path" in key.
        key = (func.__module__, func.__qualname__, bound.arguments)
        return hashlib.sha256(pickle.dumps(key)).hexdigest()

    def _cache_load(self, key: str) -> T.Any:
        path = self.cachedir / key

        if not path.is_file():
            raise KeyError

        # Update timestamps.
        with contextlib.suppress(OSError):
            os.utime(path)

        _logger.info("Returning cached result")
        with path.open("rb") as f:
            return pickle.load(f)  # noqa: S301

    def _cache_store(self, key: str, obj: object) -> None:
        path = self.cachedir / key

        with path.open("wb") as f:
            return pickle.dump(obj, f)

    def __call__[**Params, Result](
        self,
        func: T.Callable[Params, Result],
    ) -> T.Callable[Params, Result]:

        @universaldecorator
        def decorate(
            _set_args: object,
            *args: Params.args,
            **kwargs: Params.kwargs,
        ) -> T.Generator[None, Result, Result]:
            key = self._cache_key(func, *args, **kwargs)

            try:
                return self._cache_load(key)
            except KeyError:
                pass
            except OSError:
                _logger.exception("Error loading %r from cache", key)

            result = yield
            self._cache_store(key, result)
            return result

        return decorate(func)

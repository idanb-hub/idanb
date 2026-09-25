from __future__ import annotations

import logging

import typing_extensions as T

from ._decorator import decorator, universaldecorator


@decorator
def log_exceptions[**Params, Result](  # noqa: D417
    func: T.Callable[Params, Result],
    *types: type[BaseException],
    msg: object = "",
) -> T.Callable[Params, Result]:
    """Log exceptions raised in decorated functions.

    Args:
        types: Types of exceptions to log (default: `Exception`).
        msg: Message to log.
    """
    logger = logging.getLogger(func.__module__)

    if not types:
        types = (Exception,)

    @universaldecorator
    def decorate(
        _set_args: object,
        *_args: Params.args,
        **_kwargs: Params.kwargs,
    ) -> T.Generator[None, Result, Result]:
        try:
            return (yield)
        except:
            logger.exception(msg)
            raise

    return decorate(func)

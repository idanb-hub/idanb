from __future__ import annotations

import dataclasses
import functools

import typing_extensions as T


@T.dataclass_transform(
    kw_only_default=True,
    frozen_default=True,
    field_specifiers=(dataclasses.field,),
)
class Record:
    """Immutable dataclass with type-safe mutation by shallow cloning.

    All fields should have a default value set, otherwise type checkers might
    complain about missing arguments.

    >>> class Token(Record, frozen=True):
    ...    key: str = ""
    ...    age: int = 0

    >>> a0 = Token(key="a")

    Clone an instance by calling it with the attributes you want to override,
    if any.

    >>> a1 = a0(age=1)
    >>> a0, a1
    (Token(key='a', age=0), Token(key='a', age=1))

    If `frozen` is `True` (default), field assignment raises an exception,
    otherwise it doesn't (performs better, but instances are mutable).
    Type checkers should see instances as immutable in either case.

    >>> a0.age = 1
    Traceback (most recent call last):
    dataclasses.FrozenInstanceError: cannot assign to field 'age'

    """

    def __init_subclass__(cls, *, frozen: bool = True) -> None:
        _ = dataclasses.dataclass(
            cls,
            frozen=frozen,
            # Positional arguments wouldn't work in `__call__`.
            kw_only=True,
            # Generate `__hash__` even if `frozen` is `False`.
            unsafe_hash=True,
        )

    @classmethod
    def __call__[**Params, Self](
        # Unlike `self`, `cls` can be used to infer argument types.
        cls: T.Callable[Params, Self],
        /,
        # There will be no `args` since `kw_only=True`.
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> Self:
        """Create a shallow clone of self, replacing specified fields.

        Delegates to `dataclasses.replace`.
        """
        ...  # noqa: PIE790

    if not T.TYPE_CHECKING:

        @functools.wraps(__call__)
        def __call__(self, /, **kwargs: object) -> T.Self:
            return dataclasses.replace(self, **kwargs)

"""Utilities for parsing and string manipulation."""

from __future__ import annotations

import enum
import re

import typing_extensions as T


def substr_swap(
    string: str,
    left: str | T.Sequence[str],
    right: str | T.Sequence[str],
) -> str:
    """Swap occurrences of `left` and `right` in `string`.

    >>> substr_swap("aAAAaaa", "aa", "AA")
    'aaaAAAa'

    If `left` and `right` are not `str`, n-th item of `left` is swapped with
    n-th item in `right`.

    >>> substr_swap("abc", ("a", "b"), ("A", "B"))
    'ABc'

    Substring are never swapped more than once.

    >>> substr_swap("a", ("a", "b"), ("b", "c"))
    'b'
    """

    if isinstance(left, str):
        left = (left,)
    if isinstance(right, str):
        right = (right,)

    if len(left) != len(right):
        errmsg = "lengths of left and right don't match"
        raise ValueError(errmsg)

    # Replacement for `n`-th substring is at index `-n`.
    substrings = [*left, *reversed(right)]
    return re.sub(
        "|".join(f"({re.escape(s)})" for s in substrings),
        lambda match: substrings[-match.lastindex],  # pyright: ignore[reportOptionalOperand]
        string,
    )


class RegexEnum(enum.Enum):  # pyright: ignore[reportRedeclaration]
    r"""Regular expression defined as enumeration of its alternative groups.

    >>> class Token(RegexEnum):
    ...     WORD = r"\w+"
    ...     SPACE = r"\s+"
    >>> Token.re
    re.compile('(?P<WORD>\\w+)|(?P<SPACE>\\s+)')
    >>> match = re.search(Token.re, "hello world")
    >>> match
    <re.Match object; span=(0, 5), match='hello'>
    >>> assert match.lastindex == Token.WORD
    >>> assert match.lastgroup == Token.WORD
    """

    _ignore_: str | list[str] = ["pattern", "re"]  # noqa: RUF012

    re: T.ClassVar[re.Pattern[str]]
    pattern: str  # pyright: ignore[reportUninitializedInstanceVariable]

    def __new__(cls, value: str) -> T.Self:
        index = len(cls) + 1
        obj = object.__new__(cls)
        obj._value_ = index
        obj.pattern = value

        return obj

    def __init_subclass__(cls) -> None:
        patterns = [f"(?P<{member.name}>{member.pattern})" for member in cls]
        cls.re = re.compile("|".join(patterns))

    @T.override
    def __eq__(self, other: object) -> bool:
        cls = type(self)

        match other:
            case str():
                other = cls[other]
            case int():
                other = cls(other)
            case _:
                pass

        return super().__eq__(other)

    @T.override
    def __hash__(self) -> int:
        return super().__hash__()


if T.TYPE_CHECKING:
    # Otherwise pyright thinks `.re` in `RegexEnum` subclasses is `Any`.
    # IDK why, from my experience typing gets a little weird around enums.

    class RegexEnumMeta(enum.EnumType):
        re: re.Pattern[str]  # pyright: ignore[reportUninitializedInstanceVariable]

    class RegexEnum(RegexEnum, metaclass=RegexEnumMeta):
        pass

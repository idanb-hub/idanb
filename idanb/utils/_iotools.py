from __future__ import annotations

import dataclasses
import io

import typing_extensions as T


@dataclasses.dataclass()
class TextIOAdapter(io.TextIOBase):
    """Text IO stream that delegates reading and writing to provided callbacks.

    If a callback is not provided, its respective operation raises an exception.
    """

    def __init__(
        self,
        *,
        write: T.Callable[[str], int | None] | None = None,
        read: T.Callable[[int | None], str] | None = None,
    ) -> None:
        self.__write = write
        self.__read = read

    @T.override
    def writable(self) -> bool:
        return self.__write is not None

    @T.override
    def readable(self) -> bool:
        return self.__read is not None

    @T.override
    def write(self, string: str, /) -> int:
        if self.__write is None:
            errmsg = "not writable"
            raise io.UnsupportedOperation(errmsg)
        written = self.__write(string)
        return len(string) if written is None else written

    @T.override
    def read(self, size: int | None = -1, /) -> str:
        if self.__read is None:
            errmsg = "not readable"
            raise io.UnsupportedOperation(errmsg)
        return self.__read(size)

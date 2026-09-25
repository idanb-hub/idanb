from concurrent.futures import Executor
from pathlib import Path

import typing_extensions as T
from _typeshed import OpenBinaryMode, OpenTextMode
from caio.asyncio_base import AsyncioContextBase

import aiofile.utils
from aiofile.aio import AIOFile
from aiofile.utils import (
    # BinaryFileWrapper,
    FileIOCloner,
    FileIOWrapperBase,
    LineReader,
    Reader,
    # TextFileWrapper,
    Writer,
    # async_open,
    clone,
)

__all__ = [
    "AIOFile",
    "BinaryFileWrapper",
    "FileIOCloner",
    "FileIOWrapperBase",
    "LineReader",
    "Reader",
    "TextFileWrapper",
    "Writer",
    "async_open",
    "clone",
]

@T.overload
def async_open(
    file_specifier: str | Path | T.TextIO,
    mode: OpenTextMode = "r",
    encoding: str = "utf-8",
    context: AsyncioContextBase | None = None,
    executor: Executor | None = None
) -> TextFileWrapper: ...

@T.overload
def async_open(
    file_specifier: str | Path | T.BinaryIO,
    mode: OpenBinaryMode,
    context: AsyncioContextBase | None = None,
    executor: Executor | None = None
) -> BinaryFileWrapper: ...

class TextFileWrapper(aiofile.utils.TextFileWrapper):
    @T.override
    def __await__(self) -> T.Generator[None, None, T.Self]: ...
    @T.override
    async def __aenter__(self) -> T.Self: ...

class BinaryFileWrapper(aiofile.utils.BinaryFileWrapper):
    @T.override
    def __await__(self) -> T.Generator[None, None, T.Self]: ...
    @T.override
    async def __aenter__(self) -> T.Self: ...

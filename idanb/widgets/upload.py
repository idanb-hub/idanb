from __future__ import annotations

import contextlib
import copy
import logging
from pathlib import Path

import typing_extensions as T
import aiofile
import anywidget
import traitlets

from idanb import utils

if T.TYPE_CHECKING:
    import asyncio

    from reacton.core import Element


_logger = logging.getLogger(__name__)


class UploadParams(T.TypedDict, total=False, extra_items=object):
    chunk_size: int
    guard: T.Callable[[str], Path | None]


class UploadProgress(T.NamedTuple):
    done: int
    total: int


class Upload(anywidget.AnyWidget):
    """File input for uploading files from the client.

    Renders as a plain `<input type="file">` element that uploads opened files.
    """

    _esm: str | Path = Path(__file__).with_suffix(".js")

    _paths: dict[str, Path]
    _files: dict[Path, aiofile.BinaryFileWrapper]
    _writers: dict[Path, asyncio.Task[None]]

    chunk_size: traitlets.Int = traitlets.Int(
        # Larger values don't work. Is message size capped?
        default_value=(8 * 2**20),
    ).tag(sync=True)

    guard: traitlets.Callable[[str], Path | None] = traitlets.Callable()
    progress: traitlets.Dict[Path, UploadProgress] = traitlets.Dict(
        default_value={},
    )

    def __init__(
        self,
        **kwargs: T.Unpack[UploadParams],
    ) -> None:
        self._paths = {}
        self._files = {}
        self._writers = {}

        kwargs.setdefault("guard", self._default_guard)
        super().__init__(**kwargs)

        self.on_msg(type(self).on_custom_msg)

    def _default_guard(self, path: str) -> Path | None:
        return Path.cwd() / Path(path).name

    def _reject(self, path: str) -> None:
        # Negative size tells the front-end to stop uploading.
        _logger.info("Rejecting %r", path)
        self.send({"path": path, "size": -1})

    def _send_ack(self, path: str, size: int) -> None:
        self.send({"path": path, "size": size})

    @utils.log_exceptions()
    def on_custom_msg(self, content: object, buffers: list[memoryview]) -> None:
        match content:
            case {"path": str(path), "size": int(size)}:
                utils.forget_task(self._write(path, buffers, size))
            case _:
                return

    async def _get_file(self, path: str) -> aiofile.BinaryFileWrapper | None:
        filepath = self._paths.get(path)
        if filepath is not None:
            return self._files[filepath]

        filepath = self.guard(path)
        if filepath is None:
            return None

        if filepath in self._files:
            errmsg = f"file {str(filepath)!r} is locked by concurrent upload"
            raise RuntimeError(errmsg)

        _logger.info("Saving %r to %r", path, str(filepath))
        file = await aiofile.async_open(filepath, "wb")
        assert isinstance(file, aiofile.BinaryFileWrapper)

        self._paths[path] = filepath
        self._files[filepath] = file

        return file

    async def _write(
        self,
        path: str,
        buffers: list[memoryview],
        size: int,
    ) -> None:
        try:
            file = await self._get_file(path)
        except:
            self._reject(path)
            raise

        if file is None:
            self._reject(path)
            return

        filepath = self._paths[path]

        # No buffers signals EOF.
        if not buffers:
            _logger.info("Closing %r", str(filepath))

            del self._paths[path]
            del self._files[filepath]
            with self.mutate_trait(type(self).progress) as status:
                del status[filepath]

            await file.close()
            return

        for buffer in buffers:
            try:
                count = await file.write(bytes(buffer))
            except:
                self._reject(path)
                raise

            if count != len(buffer):
                _logger.warning(
                    "Incomplete write to %r (%i bytes out of %i)",
                    str(filepath),
                    count,
                    len(buffer),
                )

            with self.mutate_trait(type(self).progress) as progress:
                done, size = progress.get(filepath, (0, size))
                progress[filepath] = UploadProgress(done + len(buffer), size)

        # Signal that we're ready for the next chunk.
        self._send_ack(path, self.progress[filepath].done)

    @contextlib.contextmanager
    def mutate_trait[Value](
        self,
        trait: traitlets.TraitType[Value, Value],
    ) -> T.Generator[Value]:
        old = trait.__get__(self, type(self))
        new = copy.copy(old)
        try:
            yield new
        finally:
            trait.set(self, new)

    @T.override
    @classmethod
    def element(
        cls,
        **kwargs: T.Unpack[UploadParams],
    ) -> Element[T.Self]:
        return super().element(**kwargs)


# %run upload.ipy

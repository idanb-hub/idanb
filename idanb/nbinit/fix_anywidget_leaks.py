"""Workaround for `anywidget`'s front-end module leaking memory.

See: https://github.com/manzt/anywidget/issues/613
"""

from __future__ import annotations

import logging

import typing_extensions as T
from anywidget import AnyWidget
from anywidget._file_contents import FileContents

from idanb import meta

if T.TYPE_CHECKING:
    pass


_logger = logging.getLogger(__name__)


def patch_anywidget() -> None:
    """Patch `AnyWidget.__init__` to work around frontend memory leaks.

    Makes `__init__` replace file paths in `self._esm` and `self._css` with
    equivalent URLs, if possible.
    """
    # Abort if already patched.
    if AnyWidget.__init__.__module__ == __name__:
        _logger.warning(
            "Refusing to patch already patched function %r",
            AnyWidget.__init__.__qualname__,
        )
        return

    init = AnyWidget.__init__

    def detour(self: AnyWidget, *args: object, **kwargs: object) -> None:
        for name in ["_esm", "_css"]:
            try:
                value: object = getattr(self, name)
            except AttributeError:
                continue
            # Replace file path with URL.
            if isinstance(value, FileContents):
                url = meta.urlof(value._path)  # noqa: SLF001
                if url is not None:
                    setattr(self, name, url)

        init(self, *args, **kwargs)

    AnyWidget.__init__ = detour
    _logger.info("Patch applied to function %r", init.__qualname__)

from __future__ import annotations

import os
from pathlib import Path

import typing_extensions as T
import anywidget
import traitlets

from idanb import meta

if T.TYPE_CHECKING:
    from reacton.core import Element


class DownloadParams(T.TypedDict, total=False, extra_items=object):
    label: str
    download: str | None


class Download(anywidget.AnyWidget):
    """Download link for files from Jupyter server.

    Renders as a plain `<a>` element that downloads a file when clicked.
    """

    _esm: str | Path = Path(__file__).with_suffix(".js")

    path: traitlets.Unicode = traitlets.Unicode().tag(sync=True)
    label: traitlets.Unicode = traitlets.Unicode().tag(sync=True)
    download: traitlets.Unicode[str | None] = traitlets.Unicode(
        allow_none=True,
        default_value="",
    ).tag(sync=True)

    _baseurl: traitlets.Unicode = traitlets.Unicode().tag(sync=True)

    def __init__(
        self,
        path: str | Path,
        **kwargs: T.Unpack[DownloadParams],
    ) -> None:
        path, kwargs = self._coerce_args(path, **kwargs)

        try:
            root = meta.serverdir()
        except RuntimeError:
            # Fall back to project root, which works for local development.
            root = meta.rootdir()

        try:
            path = path.relative_to(root)
        except ValueError:
            errmsg = "path is outside of Jupyter server directory"
            raise ValueError(errmsg) from None

        baseurl = os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "/")

        super().__init__(
            path=path.as_posix(),
            _baseurl=baseurl,
            **kwargs,
        )

    @T.override
    @classmethod
    def element(
        cls,
        *,
        path: str | Path,
        **kwargs: T.Unpack[DownloadParams],
    ) -> Element[T.Self]:
        path, kwargs = cls._coerce_args(path, **kwargs)
        return super().element(path=str(path), **kwargs)

    @staticmethod
    def _coerce_args(
        path: str | Path,
        **kwargs: T.Unpack[DownloadParams],
    ) -> tuple[Path, DownloadParams]:
        path = Path(path)
        kwargs.setdefault("label", path.name)
        return path, kwargs


# %run download.ipy

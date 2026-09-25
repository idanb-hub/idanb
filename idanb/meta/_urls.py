from __future__ import annotations

import os
import urllib.parse
from collections import defaultdict
from pathlib import Path

import typing_extensions as T

from idanb import utils

from ._paths import nbpath, rootdir


@utils.cache
def nburl() -> tuple[str, dict[str, list[str]]]:
    """Get URL of the current notebook and its query parameters."""

    url = os.environ.get("VOILA_REQUEST_URL")
    if url is None:
        from ._asset_server import asset_server  # noqa: PLC0415

        urlpath = nbpath().relative_to(rootdir()).as_posix()
        base = asset_server(rootdir())
        url = urllib.parse.urljoin(base, urlpath)
        return url, {}

    scheme, authority, path, query, _fragment = urllib.parse.urlsplit(url)
    url = urllib.parse.urlunsplit((scheme, authority, path, None, None))

    params: defaultdict[str, list[str]] = defaultdict(list)
    for name, value in urllib.parse.parse_qsl(query):
        params[name].append(value)

    return url, params


@utils.cache
def baseurl() -> str:
    """Get URL corresponding to this project's root directory."""

    url, _ = nburl()

    # Strip notebook path to get the base URL.
    path = nbpath().relative_to(rootdir()).as_posix()
    if not url.endswith(path):
        errmsg = f"current URL {url!r} does match notebook path {path!r}"
        raise RuntimeError(errmsg)
    return url.removesuffix(path)


def urlof(path: str | Path) -> str:
    """Get URL corresponding to `path`."""

    path = Path(path)

    base = baseurl()
    # In Voila, `/render/` requires auth while `/files/` does not.
    base = base.replace("/voila/render/", "/voila/files/")

    url = path.relative_to(rootdir()).as_posix()
    return urllib.parse.urljoin(base, url)

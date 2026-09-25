from __future__ import annotations

import os
import sys
import tomllib
import urllib.parse
from pathlib import Path

import typing_extensions as T

from idanb import utils

if T.TYPE_CHECKING:
    pass


def _project_name(path: Path) -> str | None:
    with path.open("rb") as f:
        pyproject = tomllib.load(f)

    project: dict[object, object] | None = pyproject.get("project")
    if not isinstance(project, dict):
        return None

    name = project.get("name")
    if not isinstance(name, str):
        return None

    return name


@utils.cache
def rootdir() -> Path:
    """Get the absolute path of this project's root directory."""
    ourdir: Path | None = None

    for parent in Path(__file__).parents:
        path = parent / "pyproject.toml"
        if not path.is_file():
            continue

        name = _project_name(path)
        # Prefer parent package (with different name), fallback to this package.
        if name == "idanb":
            ourdir = parent
        else:
            return parent

    if ourdir is not None:
        return ourdir

    errmsg = "can't determine project root directory path"
    raise RuntimeError(errmsg)


@utils.cache
def pkgdir(file: str | Path) -> Path:
    """Get absolute path to the root directory of package that owns `file`."""
    file = Path(file)

    for parent in file.parents:
        path = parent / "pyproject.toml"
        if not path.is_file():
            continue

        return parent

    errmsg = "can't determine package root directory (pyproject.toml not found)"
    raise RuntimeError(errmsg)


def datadir() -> Path:
    """Get the absolute path of this project's data directory.

    The directory is created if it doesn't exist already.
    """
    path = rootdir() / "data"
    if not path.is_dir():
        path.mkdir(parents=True)

    return path


def cachedir() -> Path:
    """Get the absolute path of this project's cache directory.

    The directory is created if it doesn't exist already.
    """
    path = datadir() / ".cache"
    if not path.is_dir():
        path.mkdir(parents=True)

    return path


@utils.cache
def serverdir() -> Path:
    """Get Jupyter server root directory.

    Works only on Linux.
    """
    root = os.environ.get("JUPYTER_SERVER_ROOT")
    if root:
        return Path(root)

    pid = os.environ.get("JPY_PARENT_PID")
    if pid:
        path = Path("/proc", pid, "cwd")
        if path.exists():
            return path.readlink()

    # TODO: Windows/Mac support.

    errmsg = "can't determine server root directory"
    raise RuntimeError(errmsg)


@utils.cache
def nbpath() -> Path:
    """Get the absolute path of the current notebook."""
    # This is the notebook's module.
    main = sys.modules["__main__"]

    # Voila exposes its request URL as an environment variable.
    url = os.environ.get("VOILA_REQUEST_URL")
    if url is not None:
        # Combine filename from the URL and CWD to get the notebook path.
        urlpath = urllib.parse.urlsplit(url).path
        return Path.cwd() / Path(urlpath).name

    # Otherwise, these variables might contain the notebook path.
    for var in [
        "__session__",  # JupyterLab
        "__vsc_ipynb_file__",  # VS Code
    ]:
        path: object = vars(main).get(var)
        if path is None:
            continue
        if not isinstance(path, str):
            errmsg = f"{var!r} should be 'str', not {type(path).__qualname__!r}"
            raise TypeError(errmsg)
        return Path(path)

    for var in [
        "JPY_SESSION_NAME",
    ]:
        path = os.environ.get(var)
        if path is not None:
            return Path(path)

    errmsg = "can't determine notebook path"
    raise RuntimeError(errmsg)

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime, timedelta

import typing_extensions as T
import pygit2
from IPython.core.getipython import get_ipython
from IPython.display import DisplayHandle, display

from idanb import meta
from idanb.core import logs
from idanb.ui._js.rpc import init as rpc_init

from .components import NavigationBar
from .fix_anywidget_leaks import patch_anywidget
from .magic import IdaNBMagics

if T.TYPE_CHECKING:
    pass


_logger = logging.getLogger(__name__)


def _fix_notebook_module_name() -> None:
    """Fix the notebook's module name to enable relative imports."""
    # The main module is the notebook itself.
    main = sys.modules["__main__"]

    relpath = meta.nbpath().relative_to(meta.rootdir())
    name = ".".join(relpath.with_suffix("").parts)
    main.__name__ = name

    # Make the notebook module accessible under its new name.
    sys.modules[name] = main


def _clear_cache() -> None:
    min_atime = datetime.now(tz=UTC) - timedelta(days=1)
    for path in meta.cachedir().iterdir():
        try:
            if not path.is_file():
                continue
            atime = datetime.fromtimestamp(path.stat().st_atime, tz=UTC)
            if atime < min_atime:
                path.unlink()
        except OSError:
            _logger.exception("Error deleting old cache file %r", path.name)
        else:
            _logger.debug("Deleted old cache file %r", path.name)


def _print_notebook_version() -> DisplayHandle | None:
    path = meta.nbpath().relative_to(meta.rootdir())

    repo = meta.git.repo()
    head = repo.head.peel(pygit2.Commit)

    history = meta.git.follow(path)
    try:
        # Latest commit that modified the notebook.
        nb_commit = next(history)
    except StopIteration:
        nb_version = "??? (file not tracked by git)"
    else:
        # We already consumed the first, so +1.
        count = sum(1 for _ in history) + 1
        nb_version = f"{count}#{nb_commit.short_id}"

    repo_version = f"{sum(1 for _ in repo.walk(head.id))}#{head.short_id}"

    version = f"""
    <div id="idanb.nbinit.__init__.version" style="font-family: monospace;">
        Notebook version: {nb_version}.
        Project version: {repo_version}.
    </div>
    """
    return display({"text/html": version}, raw=True)


def nbinit() -> None:
    """Initialize the environment of the executing notebook (`__main__` module).

    See the module docstring for what that entails.
    """
    _print_notebook_version()

    _fix_notebook_module_name()

    # Set notebook's `__file__` global if missing.
    vars(sys.modules["__main__"]).setdefault("__file__", str(meta.nbpath()))

    logs.configure()

    _clear_cache()

    ip = get_ipython()
    if ip is not None:
        ip.register_magics(IdaNBMagics)

    # Must happen before any `anywidget` widgets are displayed.
    patch_anywidget()

    rpc_init()

    if meta.CONFIG.get("developer") is True:
        from .devmode import devmode  # noqa: PLC0415

        devmode()

    display(
        NavigationBar(),
    )

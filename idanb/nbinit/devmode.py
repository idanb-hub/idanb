from __future__ import annotations

import logging

import typing_extensions as T
from IPython.core.getipython import get_ipython
from IPython.extensions import autoreload

from idanb import meta, ui, utils

if T.TYPE_CHECKING:
    pass


_logger = logging.getLogger(__name__)


def autoreload_modules() -> None:
    """Enable the `autoreload` IPython extension."""
    ip = get_ipython()
    if ip is None:
        errmsg = "couldn't get current IPython instance"
        raise RuntimeError(errmsg)
    if ip.extension_manager is None:
        errmsg = "current IPython instance is missing an extension manager"
        raise RuntimeError(errmsg)

    if autoreload.__name__ not in ip.extension_manager.loaded:
        ip.extension_manager.load_extension(autoreload.__name__)

    ip.run_line_magic("autoreload", "complete")

    _logger.warning(
        "Autoreload magic is enabled. See: %s",
        "https://ipython.readthedocs.io/en/stable/config/extensions/autoreload.html",
    )


def autoreload_page() -> None:
    """Reload browser window when notebook file changes."""
    if not meta.is_voila():
        errmsg = "autoreload only works in Voila"
        raise RuntimeError(errmsg)

    def reload() -> None:
        _logger.warning("Notebook file was modified. Reloading window ...")
        ui.exec("window.location.reload()")

    utils.fs.watch(meta.nbpath(), on_modified=lambda _: reload())
    _logger.warning("Window will reload whenever the notebook file changes.")


def devmode() -> None:
    if not meta.is_voila():
        autoreload_modules()

    if meta.is_voila():
        autoreload_page()

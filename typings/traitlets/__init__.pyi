# ruff: noqa
# ruff: noqa: PGH004

import typing_extensions as T

import traitlets.traitlets as traitlets
from traitlets._version import __version__, version_info
from traitlets.traitlets import *
from traitlets.utils.bunch import Bunch
from traitlets.utils.importstring import import_item
from traitlets.utils.decorators import signature_has_traits

__all__ = [
    "traitlets",
    "__version__",
    "version_info",
    "Bunch",
    "signature_has_traits",
    "import_item",
    "Sentinel",
]
__all__ += traitlets.__all__

Sentinel = traitlets.Sentinel

class _HasTraits(traitlets.HasTraits):
    # Workaround for Pyright ignoring `__init__` annotations.
    # Already fixed upstream: https://github.com/ipython/traitlets/pull/918
    # Once new version is released, this can be removed.
    def __new__(cls, *args: T.Any, **kwargs: T.Any) -> T.Self: ...

HasTraits = _HasTraits

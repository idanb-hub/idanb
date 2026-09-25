from __future__ import annotations

import typing_extensions as T

from idanb import meta, utils

if T.TYPE_CHECKING:
    pass


# Set empty CONFIG to avoid loading `config.yaml`.
meta.CONFIG = utils.config.Config({})

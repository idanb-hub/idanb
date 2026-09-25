"""Notebook environment initialization.

The first cell of every notebook should be:

```py
from __future__ import annotations

from idanb.nbinit import logger
```
"""

from __future__ import annotations

import os
import sys

import typing_extensions as T
import loguru

from .nbinit import nbinit

if T.TYPE_CHECKING:
    pass


# Run `nbinit()` on import, unless ...
if (
    # Running under pytest.
    "PYTEST_VERSION" not in os.environ
    # Notebook defines `NBINIT_SKIP = True`.
    and vars(sys.modules["__main__"]).get("NBINIT_SKIP") is not True
):
    nbinit()


logger = loguru.logger

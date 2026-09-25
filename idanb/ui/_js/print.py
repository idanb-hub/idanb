from __future__ import annotations

from pathlib import Path

import typing_extensions as T

from .rpc import exec as jsexec

if T.TYPE_CHECKING:
    pass


PRINT_JS = Path(__file__).with_suffix(".js").read_text()
PRINT_CSS = Path(__file__).with_suffix(".css").read_text()


def print() -> None:  # noqa: A001
    """Print browser page to PDF."""
    jsexec(PRINT_JS, css=PRINT_CSS)

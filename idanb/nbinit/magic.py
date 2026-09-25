from __future__ import annotations

import typing_extensions as T
from IPython.core import magic

from idanb import meta

if T.TYPE_CHECKING:
    from IPython.core.interactiveshell import InteractiveShell


@magic.magics_class
class IdaNBMagics(magic.Magics):
    # Base class is missing type annotations.
    shell: InteractiveShell | None

    @magic.line_cell_magic
    def demo(self, line: str, cell: str | None = None) -> None:
        """Skip executing code in Voila."""
        if self.shell is None:
            return

        if meta.is_voila():
            return

        if cell is None:
            cell = line

        self.shell.run_cell(cell)

    @magic.cell_magic("if")
    def if_(self, line: str, cell: str) -> None:
        """Don't execute cell unless condition is satisfied."""
        if self.shell is None:
            return

        if eval(line):  # noqa: S307
            self.shell.run_cell(cell)

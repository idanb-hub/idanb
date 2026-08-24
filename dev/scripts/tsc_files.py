#!/usr/bin/env python3

"""Run `tsc` on specific files without ignoring `tsconfig.json`.

usage: tsc_files.py [FILE] ...

arguments:
  FILE                file to include in compilation
"""  # noqa: D405

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def log(*values: object) -> None:
    print(*values, file=sys.stderr)  # noqa: T201


def main() -> int:
    args = sys.argv[1:]

    if not args:
        assert __doc__ is not None, "module docstring missing"
        log(__doc__.replace("tsc_files.py", sys.argv[0]).strip())
        return 2

    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=Path.cwd(),
        prefix="tsconfig.",
        suffix=".json",
    ) as tsconfig:
        json.dump(
            {
                "extends": Path("./tsconfig.json").absolute(),
                "include": [Path(arg).absolute() for arg in args],
            },
            tsconfig,
            default=str,
        )
        tsconfig.flush()

        tsc = shutil.which("tsc") or "tsc"
        proc = subprocess.run([tsc, "--project", tsconfig.name], check=False)  # noqa: S603
        return proc.returncode


if __name__ == "__main__":
    sys.exit(main())

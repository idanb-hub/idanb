#!/usr/bin/env python3

"""Process plaintext Jupytext notebooks using tools for regular notebooks.

usage: jupytext_run.py COMMAND [-FLAG | "-FLAG FLAG" | FILE] ...

arguments:
  COMMAND             command to run on each FILE (after conversion to `.ipynb`)
  FLAG                flag to append to each invocation of COMMAND
  FILE                plaintext notebook to process
"""  # noqa: D405

import shlex
import shutil
import subprocess
import sys


def log(*values: object) -> None:
    print(*values, file=sys.stderr)  # noqa: T201


def parse_args(args: list[str]) -> tuple[str, list[str]]:
    if not args:
        errmsg = "command not specified"
        raise RuntimeError(errmsg)

    cmd, *args = args

    flags: list[str] = []
    files: list[str] = []
    for arg in args:
        if arg.startswith("-"):
            flags.append(arg)
        else:
            files.append(arg)

    # Jupytext replaces `{}` with the notebook filename.
    cmd = " ".join((cmd, *flags, "{}"))
    return cmd, files


def main() -> int:
    args = sys.argv[1:]

    if not args:
        assert __doc__ is not None, "module docstring missing"
        log(__doc__.replace("jupytext_run.py", sys.argv[0]).strip())
        return 2

    cmd, files = parse_args(args)

    args = [
        "jupytext",
        "--pipe",
        cmd,
        "--pipe-fmt",
        "ipynb",
        *files,
    ]

    log(shlex.join(args))

    executable = shutil.which(args[0])
    if executable is not None:
        args[0] = executable

    proc = subprocess.run(args, check=False)  # noqa: S603
    return proc.returncode


if __name__ == "__main__":
    try:
        exitcode = main()
    except RuntimeError as e:
        log(str(e))
        sys.exit(1)
    else:
        sys.exit(exitcode)

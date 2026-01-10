#!/usr/bin/env python3

# ruff: noqa: T201

from __future__ import annotations

import contextlib
import functools
import itertools
import os
import shlex
import shutil
import subprocess
import sys
import typing
from pathlib import Path

if typing.TYPE_CHECKING:
    import typing_extensions as T


def log(*values: object) -> None:
    print(*values, file=sys.stderr)


# Project root directory.
ROOT = Path(__file__).parent
assert ROOT.joinpath("pyproject.toml").is_file(), "script isn't in project root"

# Whether we're running inside JupyerHub.
JUPYTERHUB = "JUPYTERHUB_HOST" in os.environ


def split(*args: str | T.Iterable[str]) -> T.Iterable[str]:
    """Split strings and flatten other iterables.

    >>> list(split("one two", ["three", "four"]))
    ['one', 'two', 'three', 'four']
    >>> list(split(["one two"]))
    ['one two']
    """
    return itertools.chain.from_iterable(
        shlex.split(arg) if isinstance(arg, str) else arg for arg in args
    )


def run(
    *cmd: str | T.Iterable[str],
    quiet: bool = False,
    cwd: str | Path | None = None,
) -> None:
    args = list(split(*cmd))
    if not args:
        errmsg = "no args"
        raise ValueError(errmsg)

    if not quiet:
        log(f">>> {shlex.join(args)}")

    pipe = subprocess.DEVNULL if quiet else None

    _ = subprocess.run(
        args=args,
        shell=False,
        check=True,
        stdout=pipe,
        stderr=pipe,
        cwd=cwd,
    )


@functools.cache
def uv() -> str:
    """Find command that invokes `uv`.

    Raises:
        FileNotFoundError: Cannot find `uv`.
    """
    for cmd in ["uv", "python -m uv"]:
        try:
            run(cmd, "--version", quiet=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            continue
        else:
            return cmd

    # If we returned `None`, it would get cached.
    errmsg = "uv not found"
    raise FileNotFoundError(errmsg)


def sync_deps(
    *,
    local: bool = not JUPYTERHUB,
) -> None:
    """Sync project dependencies with `uv sync`.

    Args:
        local: Whether to install the `local` extra. Defaults to `False`
            if running in JupyterHub and `True` otherwise.
    """
    extras: list[str] = []

    if local:
        extras.append("local")

    run(uv(), "sync", map("--extra={}".format, extras), "--locked")


def sync_notebooks(*, root: str | Path = ROOT) -> None:
    """Sync `ipynb` and Markdown notebooks.

    For each notebook, whichever variant was last modified is kept while the
    other is overwritten. To force conversion one way or the other, delete the
    unwated variant first.

    Args:
        root: Project root directory. Autodetected by default.
    """
    root = Path(root)

    notebooks = (
        path.relative_to(root) for path in root.glob("notebooks/**/*.md")
    )
    # Jupytext doesn't handle backslashes very well.
    # See: https://github.com/mwouts/jupytext/pull/1378
    notebooks = map(Path.as_posix, notebooks)

    # NOTE: This keeps whichever notebook variant was last modified.
    run(uv(), "run jupytext --sync", notebooks, cwd=root)


def update() -> None:
    sync_deps()
    sync_notebooks()


@contextlib.contextmanager
def errmsg(msg: str) -> T.Generator[None]:
    """Wrap any potentially thrown exception `e` in `RuntimeError(msg) from e`.

    >>> with errmsg("oops"):
    ...     x = 1 / 0
    Traceback (most recent call last):
    RuntimeError: oops
    """
    try:
        yield
    except Exception as e:
        raise RuntimeError(msg) from e


def main() -> int:
    # Make sure `uv` is available before running any commands.
    try:
        with errmsg("Requirements not satisfied"):
            _ = uv()
    except RuntimeError:
        if not JUPYTERHUB:
            raise

        # In JuputerHub, there's no harm installing things globally.
        run("pip install --user uv")

    # Install and set up dependencies.

    with errmsg("Failed to install project dependencies"):
        sync_deps()

    with errmsg("Failed to register kernel"):
        # Generates kernel.json in our virtual environment.
        run(uv(), "run python -m ipykernel install --sys-prefix")

    with errmsg("Failed to generate notebooks"):
        sync_notebooks()

    config = ROOT / "config.yaml"
    with errmsg("Failed to create default config"):
        if not config.exists():
            _ = shutil.copy(ROOT / "config.example.yaml", config)

    return 0


if __name__ == "__main__":
    try:
        exitcode = main()
    except KeyboardInterrupt:
        exitcode = 1
    except RuntimeError as e:
        exitcode = 1

        # Include more details but not full traceback. That would be too scary.
        log(e)
        e = e.__cause__
        while e is not None:
            log(f"^ caused by {type(e).__name__}: {e}")
            e = e.__cause__

    sys.exit(exitcode)

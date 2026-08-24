#!/usr/bin/env python3
# +
"""Bootstrap the notebook environment.

This file can be imported or executed as either a script or a notebook.
"""

from __future__ import annotations

import contextlib
import functools
import os
import shlex
import shutil
import subprocess
import sys
import threading
import typing  # noqa: TID251
from pathlib import Path

if typing.TYPE_CHECKING:
    import typing_extensions as T
# -


# + [markdown]
# <style>
# /**
#  * CSS to pin scrolling to bottom.
#  * https://css-tricks.com/books/greatest-css-tricks/pin-scrolling-to-bottom/
#  */
# #rendered_cells * {
#     overflow-anchor: none;
# }
# #rendered_cells::after {
#     content: '';
#     display: block;
#     height: 1px;
#     overflow-anchor: auto;
# }
# #rendered_cells > :first-child {
#     min-height: 100%;
#     margin-top: 1px;
# }
# /* Hide skeletons under loading cells. */
# .voila-skeleton-container {
#     display: none;
# }
# </style>
# -


# HTML to display before running commands.
PROLOG = """\
<script type="module">
    // Auto-start scrolling to bottom.
    const scroller = document.getElementById("rendered_cells");
    scroller.scrollTo(0, scroller.scrollHeight);
</script>
"""


# HTML to display after running commands.
EPILOG = f"""\
<a target="_self" href="{os.environ.get("JUPYTERHUB_BASE_URL", "/")}">
    Continue to JupyterLab
</a>
"""


@functools.cache
def is_notebook() -> bool:
    """Is this script running as a notebook (via Jupytext)."""
    return "__file__" not in globals()


@functools.cache
def is_jupyterhub() -> bool:
    return "JUPYTERHUB_HOST" in os.environ


@functools.cache
def is_voila() -> bool:
    return "VOILA_REQUEST_URL" in os.environ


@functools.cache
def rootdir() -> Path:
    if not is_notebook():
        return Path(__file__).parent

    # Notebooks run in their directory.
    return Path.cwd()


if is_notebook():
    # TLJH ships with `ipywidgets`.
    # https://github.com/jupyterhub/the-littlest-jupyterhub/blob/2.0.0/tljh/requirements-user-env-extras.txt#L27
    import ipywidgets
    from IPython.display import display

    # In Voila, even with progressive rendering enabled, cell's output is shown
    # only after that cell finishes executing. To avoid buffering logs, we write
    # them into an output widget instead.
    out = ipywidgets.Output()
    display(out)
else:
    # Display can be used in notebooks only.
    def display(*args: T.Any, **kwargs: T.Any) -> T.Any:
        raise NotImplementedError


def log(*values: object, end: str = "\n", error: bool = False) -> None:
    if is_notebook():
        # Error logs are shown in red.
        append_output = out.append_stderr if error else out.append_stdout
        append_output(" ".join(map(str, values)) + end)
    else:
        print(*values, end=end, file=sys.stderr)  # noqa: T201


def split(*args: str | Path | T.Iterable[str]) -> T.Iterable[str]:
    """Split strings and flatten other iterables.

    >>> list(split("one two", ["three", "four"]))
    ['one', 'two', 'three', 'four']
    >>> list(split(["one two"]))
    ['one two']
    >>> list(split(Path("one two")))
    ['one two']
    """
    for arg in args:
        match arg:
            case str():
                yield from shlex.split(arg)
            case Path():
                yield str(arg)
            case _:
                yield from arg


def run(
    *cmd: str | Path | T.Iterable[str],
    quiet: bool = False,
    cwd: str | Path | None = None,
    shell: bool = False,
) -> None:
    args = list(split(*cmd))
    if not args:
        errmsg = "no args"
        raise ValueError(errmsg)

    if shell:
        # Join args using double quotes so that shell environment variable
        # expansion works.
        args = shlex.join(args).replace("'", '"')

    if not quiet:
        log(f">>> {args if isinstance(args, str) else shlex.join(args)}")

    if not isinstance(args, str):
        # Expand executable name for consistency between UNIX and Windows.
        executable = shutil.which(args[0])
        if executable is not None:
            args[0] = executable

    with subprocess.Popen(
        args=args,
        cwd=cwd,
        shell=isinstance(args, str),
        stdout=subprocess.DEVNULL if quiet else subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    ) as proc:
        if proc.stdout is not None:
            # Capture output and log it to avoid buffering in Voila.
            for line in iter(proc.stdout.readline, ""):
                log(line, end="")

        returncode = proc.wait()
        if returncode != 0:
            raise subprocess.CalledProcessError(returncode, args)


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
    local: bool | None = None,
) -> None:
    """Sync project dependencies with `uv sync`.

    Args:
        local: Whether to install the `local` extra. Defaults to `False`
            if running in JupyterHub and `True` otherwise.
    """
    if local is None:
        local = not is_jupyterhub()

    extras: list[str] = []

    if local:
        extras.append("local")

    run(uv(), "sync", map("--extra={}".format, extras), "--locked")


def sync_notebooks(*, root: str | Path | None = None) -> None:
    """Sync `ipynb` and Markdown notebooks.

    For each notebook, whichever variant was last modified is kept while the
    other is overwritten. To force conversion one way or the other, delete the
    unwanted variant first.

    Args:
        root: Project root directory. Autodetected by default.
    """
    root = rootdir() if root is None else Path(root)

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


def bootstrap() -> None:
    # Make sure `uv` is available before running any commands.
    try:
        with errmsg("Requirements not satisfied"):
            _ = uv()
    except RuntimeError:
        if not is_jupyterhub():
            raise

        # In JupyterHub, there's no harm installing things globally.
        run("pip install --user uv")

    # Install and set up dependencies.

    with errmsg("Failed to install project dependencies"):
        sync_deps()

    with errmsg("Failed to register kernel"):
        # Generates kernel.json in our virtual environment.
        run(
            uv(),
            "run python -m ipykernel",
            "install",
            "--sys-prefix",
            # For consistency with VS Code, which uses this name.
            "--display-name .venv",
        )

    with errmsg("Failed to generate notebooks"):
        sync_notebooks()

    config = rootdir() / "config.yaml"
    with errmsg("Failed to create default config"):
        if not config.exists():
            _ = shutil.copy(rootdir() / "config.example.yaml", config)

    if is_jupyterhub():
        with errmsg("Failed to symlink virtual environment into Jupyter"):
            # Assumes that JupyterHub defines these environment variables:
            #   JUPYTER_PATH=$HOME/.local/state/jupyter_venv/share/jupyter
            #   JUPYTER_CONFIG_PATH=$HOME/.local/state/jupyter_venv/etc/jupyter
            target = Path("~/.local/state/jupyter_venv").expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            run("ln -srTf .venv", target, cwd=rootdir())


@contextlib.contextmanager
def logerror() -> T.Generator[None]:
    try:
        yield
    except RuntimeError as e:
        log(e, error=True)
        # Include more details but not full traceback. That would be too scary.
        e = e.__cause__
        while e is not None:
            log(f"^ caused by {type(e).__name__}: {e}", error=True)
            e = e.__cause__


if __name__ == "__main__" and is_notebook():
    display({"text/html": PROLOG}, raw=True)


if __name__ == "__main__":
    with logerror():
        try:
            bootstrap()
        except KeyboardInterrupt:
            exitcode = 1
        except RuntimeError:
            exitcode = 1
            # Re-raise for the context manager to handle it.
            raise
        else:
            exitcode = 0

    if not is_notebook():
        sys.exit(exitcode)


if __name__ == "__main__" and is_notebook():
    display({"text/html": EPILOG}, raw=True)


def stop_server() -> None:
    """Stop this JupyterHub server.

    Because some changes take effect only after a server restart.
    Requires `$JUPYTERHUB_API_TOKEN` to have the `delete:servers!server` role.
    """
    with errmsg("Failed to stop JupyterHub server"):
        run(  # noqa: S604
            "curl -X DELETE",
            # Server stops before progress can be cleared.
            "--no-progress-meter",
            ["-H", "Authorization: Bearer $JUPYTERHUB_API_TOKEN"],
            "$JUPYTERHUB_API_URL/users/$JUPYTERHUB_USER/server",
            shell=True,
        )


if __name__ == "__main__" and is_jupyterhub() and is_voila():
    with logerror():
        # Run in a thread so that this cell finishes executing while the server
        # is still running. Otherwise the skeleton/placeholder cell output in
        # Voila stays forever visible.
        thread = threading.Thread(target=stop_server)
        thread.start()

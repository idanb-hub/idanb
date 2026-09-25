# ruff: noqa: ARG001 I002

"""Voila configuration file.

See:
  https://voila.readthedocs.io/en/stable/customize.html
  https://github.com/voila-dashboards/voila/blob/main/voila/configuration.py
"""

from __future__ import annotations

import functools
import json
import os
import random
import shlex
import subprocess
import textwrap
import typing  # noqa: TID251
from pathlib import Path

# In JupyterHub, this file does not run in the project's virtual environment.
# Jupyter packages should be available, since they're used by JupyterHub itself.
import nbformat

if typing.TYPE_CHECKING:
    import logging
    from collections.abc import Iterable

    import tornado
    from traitlets.config import Config
    from voila.configuration import VoilaConfiguration


vc: VoilaConfiguration

if "c" in globals():
    # When loaded by Voila, `c` is predefined.
    if typing.TYPE_CHECKING:
        c: Config = typing.cast("typing.Any", ...)
    vc = c.VoilaConfiguration
else:
    # Create dummy config when debugging outside Voila.
    from traitlets.config import Config

    vc = typing.cast("typing.Any", Config())

vc.progressive_rendering = True
vc.show_tracebacks = True
vc.file_allowlist = [r".*\.(js|css)"]
vc.extension_language_mapping = {
    ".ipy": "python",
    ".md": "python",
    ".py": "python",
}


@functools.cache
def get_venv() -> Path | None:
    """Resolve path to this project's virtual environment."""
    for parent in Path(__file__).resolve().parents:
        if parent.joinpath("pyvenv.cfg").is_file():
            return parent

    return None


def run(*code: str, args: Iterable[str] = ()) -> str:
    """Run Python `code` in project venv and return its stdout."""
    venv = get_venv()
    if venv is None:
        activate = ""
    elif os.name == "nt":
        activate = f'"{venv / "Scripts" / "activate"}" && '
    else:
        activate = f'. "{venv / "bin" / "activate"}" && '

    try:
        proc = subprocess.run(  # noqa: S602
            f"{activate} python - {shlex.join(args)}",
            shell=True,
            input="\n".join(code),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        if e.stderr:
            e.add_note(e.stderr)
        raise e from None

    return proc.stdout


def get_config(*path: str) -> object:
    """Get values from project config."""
    stdout = run(
        "import json",
        "import sys",
        "from idanb.meta import CONFIG",
        "json.dump(CONFIG.get(*sys.argv[1:], default=None), sys.stdout)",
        args=path,
    )
    return json.loads(stdout)


def page_config_hook(  # noqa: PLR0913, PLR0917
    current_page_config: dict[str, typing.Any],
    base_url: str,
    settings: dict[str, typing.Any],
    log: logging.Logger,
    voila_configuration: VoilaConfiguration,
    notebook_path: str,
) -> dict[str, typing.Any]:
    # Sync Voila theme with config before rendering a notebook.
    try:
        theme = get_config("theme")
    except subprocess.CalledProcessError:
        log.exception("Can't read config")
    else:
        if isinstance(theme, str):
            voila_configuration.theme = theme

    return current_page_config


vc.page_config_hook = page_config_hook


def prelauch_hook(
    req: tornado.web.RequestHandler,
    notebook: nbformat.NotebookNode,
    cwd: str,
) -> None:
    prologue = [
        # Inject custom CSS.
        nbformat.NotebookNode(
            # Custom template would be cleaner, but this works too.
            # See: https://github.com/voila-dashboards/voila/issues/327
            cell_type="markdown",
            source=textwrap.dedent("""\
            <style>
                /* Hide this cell. */
                div#rendered_cells div[cell-index='1'] {
                    display: none;
                }
                /* Don't override MUI background color. */
                div#rendered_cells, div#main {
                    background-color: inherit;
                }
                /* Let MUI overflow its containing widgets. */
                div.lm-Widget {
                    overflow: visible;
                }
            </style>
            """),
        ),
        # Auto-import `idanb.nbinit`.
        nbformat.NotebookNode(
            cell_type="code",
            source=textwrap.dedent("""\
            try:
                from idanb import meta
            except ModuleNotFoundError:
                pass
            else:
                # Don't import in top-level notebooks.
                if meta.nbpath().parent != meta.rootdir():
                    import idanb.nbinit
                del meta
            """),
        ),
    ]

    for node in prologue:
        node["id"] = random.randbytes(4).hex()  # noqa: S311
        node.setdefault("metadata", {})
        if node["cell_type"] == "code":
            node["execution_count"] = None
            node["outputs"] = []

    notebook["cells"] = [*prologue, *notebook["cells"]]


vc.prelaunch_hook = prelauch_hook

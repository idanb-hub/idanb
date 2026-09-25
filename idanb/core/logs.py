from __future__ import annotations

import logging
import logging.config
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import typing_extensions as T
import loguru
import yaml

from idanb import meta, utils

if T.TYPE_CHECKING:
    from tempfile import _TemporaryFileWrapper


_logger = logging.getLogger(__name__)


def configure() -> None:
    path = meta.rootdir() / "config" / "logging.yaml"
    with path.open("rb") as f:
        config: dict[str, object] = yaml.safe_load(f)

    # Dummy key for defining anchors.
    config.pop(".defs")
    config["disable_existing_loggers"] = False

    logging.config.dictConfig(config)

    class PropagateHandler(logging.Handler):
        @T.override
        def emit(self, record: logging.LogRecord) -> None:
            logging.getLogger(record.name).handle(record)

    loguru.logger.remove()
    loguru.logger.add(PropagateHandler(), format="{message}")

    _logger.warning(
        "Log file %r will be deleted when kernel shuts down",
        str(logpath()),
    )


@utils.cache
def logfile() -> _TemporaryFileWrapper[str]:
    file = tempfile.NamedTemporaryFile(  # noqa: SIM115
        mode="w",
        # Store log next to notebook.
        dir=meta.nbpath().parent,
        prefix=f"{meta.nbpath().name}.",
        suffix=".log",
    )

    # Make sure file gets cleaned up.
    _delete_file_on_exit(file.name)

    return file


def _delete_file_on_exit(path: str) -> None:
    """Start a child process that unlinks `path` when we exit.

    Unlike `atexit`, this works even if we get SIGKILLed.
    """
    _ = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-c",
            textwrap.dedent("""\
            import contextlib, os, sys
            _, path = sys.argv
            with contextlib.suppress(BaseException):
                # Blocks until parent closes pipe.
                sys.stdin.read()
            with contextlib.suppress(FileNotFoundError):
                os.unlink(path)
            """),
            path,
        ],
        stdin=subprocess.PIPE,
    )


def logpath() -> Path:
    file = logfile()
    return Path(file.name)


class TempFileHandler(logging.StreamHandler["_TemporaryFileWrapper[str]"]):
    def __init__(self) -> None:
        file = logfile()
        super().__init__(file)

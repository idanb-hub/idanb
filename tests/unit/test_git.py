from __future__ import annotations

import functools
import shutil
import subprocess
from pathlib import Path

import typing_extensions as T
import pytest

from idanb import meta

if T.TYPE_CHECKING:
    pass


def gitrun(*args: str | Path) -> str:
    executable = shutil.which("git")
    if executable is None:
        errmsg = "git executable not found in PATH"
        raise FileNotFoundError(errmsg)

    proc = subprocess.run(  # noqa: S603
        [executable, *args],
        cwd=meta.rootdir(),
        check=True,
        capture_output=True,
        text=True,
    )

    return proc.stdout


try:
    gitrun("--version")
except Exception:  # noqa: BLE001
    pytest.skip("can't run git", allow_module_level=True)


def lines(string: str) -> list[str]:
    return [line for line in string.split("\n") if line]


@functools.cache
def gitfiles() -> list[Path]:
    files = gitrun("ls-files")
    return [Path(path) for path in lines(files)]


@pytest.mark.parametrize("path", gitfiles(), ids=map(str, gitfiles()))
def test_follow(path: Path) -> None:
    commits = [
        [commit.short_id, commit.message.split("\n", maxsplit=1)[0]]
        for commit in meta.git.follow(path)
    ]

    log = gitrun("log", "--oneline", "--", path)
    expected = [line.split(maxsplit=1) for line in lines(log)]
    assert commits == expected

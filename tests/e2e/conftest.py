from __future__ import annotations

import multiprocessing
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
from http import HTTPStatus
from pathlib import Path

import typing_extensions as T
import pytest

from idanb import meta

if T.TYPE_CHECKING:
    from playwright.async_api import Page
    from pytest_print import Printer


class Server(T.NamedTuple):
    address: str
    token: str


@pytest.fixture(scope="session")
def server() -> T.Generator[Server]:
    with subprocess.Popen(
        [
            sys.executable,
            "-P",  # don't prepend CWD to `sys.path`
            "-m",
            "jupyterlab",
            "--no-browser",
            "--allow-root",  # CI runs as root
        ],
        stderr=subprocess.PIPE,
        text=True,
        cwd=meta.rootdir(),
        env={
            name: value
            for name, value in os.environ.items()
            # Don't let notebooks know they're running under pytest.
            if not name.startswith("PYTEST")
        },
    ) as proc:
        assert proc.stderr is not None
        stderr: T.IO[str] = proc.stderr

        for line in stderr:
            sys.stderr.write(line)

            match = re.fullmatch(
                r"(http://[^/]+)/lab\?token=(\w+)",
                line.strip(),
            )
            if match is None:
                continue

            # Keep reading from pipe to avoid blocking child when buffer fills.
            multiprocessing.Process(target=_printlines, args=[stderr]).start()

            address, token = match.groups()
            yield Server(address, token)
            break

        proc.terminate()


def _printlines(io: T.IO[str]) -> None:
    for line in io:
        sys.stderr.write(line)


@pytest.fixture(scope="session")
def base_url(server: Server) -> str:
    """Fixture used by Playwright as base URL for `page.goto`."""
    return urllib.parse.urljoin(server.address, "voila/render/")


@pytest.fixture
async def page(page: Page, server: Server) -> Page:
    await page.set_extra_http_headers(
        {"Authorization": f"Bearer {server.token}"},
    )
    return page


@pytest.fixture(scope="session", autouse=True)
# Doesn't run unless name starts with an underscore. No idea why.
def _install_browser(
    printer_session: Printer,
    # Fixture provided by Playwright.
    browser_name: str,
) -> None:
    """Install browsers before running tests."""
    with subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "playwright", "install", browser_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    ) as proc:
        assert proc.stdout is not None
        stdout: T.IO[str] = proc.stdout
        for line in stdout:
            printer_session(line.removesuffix("\n"))


@pytest.fixture
def query() -> dict[str, object]:
    """URL query parameters for the tested notebook."""
    return {}


@pytest.fixture(autouse=True)
async def goto_test_script(
    request: pytest.FixtureRequest,
    page: Page,
    query: dict[str, object],
) -> Page:
    """Automatically navigate to the test's IPython script."""
    path = request.path.with_suffix(".ipy")
    url = path.relative_to(meta.rootdir()).as_posix()

    if query:
        url += "?" + urllib.parse.urlencode(query)

    response = await page.goto(url)
    assert response
    assert response.status == HTTPStatus.OK

    return page


@pytest.fixture
def tempdir() -> T.Generator[Path]:
    with tempfile.TemporaryDirectory() as path:
        yield Path(path)

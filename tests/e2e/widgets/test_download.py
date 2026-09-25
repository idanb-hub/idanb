from __future__ import annotations

import filecmp
from pathlib import Path

import typing_extensions as T

if T.TYPE_CHECKING:
    from playwright.async_api import Page


async def test_download(page: Page, tempdir: Path) -> None:
    download = await page.wait_for_selector("a[download]")
    assert download is not None

    srcfile = Path(__file__).with_suffix(".ipy")
    dstfile = tempdir / srcfile.name

    async with page.expect_download() as event:
        await download.click()
        file = await event.value
        assert file.suggested_filename == srcfile.name
        await file.save_as(tempdir / file.suggested_filename)

    assert filecmp.cmp(srcfile, dstfile), "downloaded file doesn't match"

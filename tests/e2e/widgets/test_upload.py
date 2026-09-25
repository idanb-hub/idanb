from __future__ import annotations

import filecmp
from pathlib import Path

import typing_extensions as T
import pytest
from playwright.async_api import expect

if T.TYPE_CHECKING:
    from playwright.async_api import Page


@pytest.fixture
def query(tempdir: Path) -> dict[str, object]:
    return {
        "tempdir": tempdir,
    }


async def test_upload(page: Page, tempdir: Path) -> None:
    upload = await page.wait_for_selector("input[type='file']")
    assert upload is not None

    srcfile = Path(__file__)
    dstfile = tempdir / srcfile.name

    async with page.expect_file_chooser() as event:
        await upload.click()
        file_chooser = await event.value
        await file_chooser.set_files(srcfile)

    label = page.get_by_text(str(dstfile), exact=True)
    await expect(label).to_be_visible()
    # Get progress bar by XPath as child of next sibling.
    bar = label.locator("//following-sibling::*[1]/*")
    await expect(bar).to_be_visible()

    # Wait for upload to complete.
    await expect(bar).to_contain_class("progress-bar-success")

    assert filecmp.cmp(srcfile, dstfile), "uploaded file doesn't match"

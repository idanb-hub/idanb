from __future__ import annotations

import typing_extensions as T
from playwright.async_api import expect

if T.TYPE_CHECKING:
    from playwright.async_api import Page


async def test_datagrid(page: Page) -> None:
    datagrid = page.locator("//perspective-viewer-datagrid")
    await expect(datagrid).to_be_visible()

    red = datagrid.get_by_text("red")
    await expect(red).to_have_css("color", "rgb(255, 0, 0)")
    await expect(red).to_have_css("font-weight", "700")

    yellow = datagrid.get_by_text("yellow")
    await expect(yellow).not_to_be_visible()

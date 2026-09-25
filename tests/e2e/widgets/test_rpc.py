from __future__ import annotations

import typing_extensions as T
import pytest
from playwright.async_api import expect

if T.TYPE_CHECKING:
    from playwright.async_api import Locator, Page


type RPC = T.Callable[[str], T.Awaitable[None]]


@pytest.fixture
async def rpc(page: Page) -> RPC:

    async def rpc(expr: str) -> None:
        textarea = await page.wait_for_selector("textarea")
        assert textarea is not None

        button = page.get_by_text("Submit", exact=True)
        await expect(button).to_be_enabled()

        await textarea.type(expr, delay=10.0)
        await button.click()

    return rpc


@pytest.fixture
def output(page: Page) -> Locator:
    return page.locator(".test-output")


async def test_simple(page: Page, rpc: RPC) -> None:
    async with page.expect_event("dialog") as event:
        await rpc("alert(1 + 2)")
        dialog = await event.value
        assert dialog.type == "alert"
        assert dialog.message == "3"
        await dialog.accept()


async def test_func(rpc: RPC, output: Locator) -> None:
    await rpc("print('hello world')")
    await expect(output).to_have_text("hello world")

from __future__ import annotations

from pathlib import Path

import typing_extensions as T
import aiofile
import ipymui
import reacton
from ipymui.components import mui

from idanb import react, widgets


@reacton.component
def FileContentsDialog(  # noqa: N802
    *,
    path: str | Path,
    title: str | None = None,
    open: bool,
    on_close: T.Callable[..., None],
) -> None:
    path = Path(path)
    if title is None:
        title = path.name

    text, set_text = react.use_state("")

    @react.use_task()
    async def read() -> None:
        if not open:
            return

        async with aiofile.async_open(path, "r") as f:
            text = await f.read()
            set_text(text)

    react.use_effect(lambda: read.start(), [path, open])

    with mui.Dialog(
        open=open,
        onClose=on_close,
        scroll="paper",
        maxWidth=False,
        fullWidth=True,
        slotProps=dict(
            # Always max possible height (default `max-height` still applies).
            paper=dict(
                sx=dict(
                    height="100%",
                ),
            ),
        ),
    ):
        with (
            mui.DialogTitle(),
            mui.Stack(
                direction="row",
                alignItems="baseline",
                justifyContent="space-between",
            ),
        ):
            mui.Typography(title, variant="h6")
            with mui.Stack(
                spacing=1,
                direction="row",
            ):
                with mui.Tooltip(title="Download"):
                    with mui.IconButton(
                        mui.icons.Download(),
                        ariaLabel="Download",
                        onClick=ipymui.JavaScript(
                            "$[0].currentTarget.querySelector('a').click()"
                        ),
                    ):
                        widgets.Download.element(
                            path=path,
                            label="",
                        )

        with mui.DialogContent(
            dividers=True,
        ):
            with mui.DialogContentText():
                with mui.Typography(
                    variant="body2",
                    sx=dict(
                        fontFamily="monospace",
                        whiteSpace="pre-wrap",
                        wordBreak="break-all",
                    ),
                ):
                    widgets.TextStream.element(value=text)

        with mui.DialogActions():
            mui.Button(
                "Close",
                onClick=on_close,
            )


# %run file_contents_dialog.ipy

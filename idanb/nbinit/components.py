from __future__ import annotations

import typing_extensions as T
from ipymui.components import mui

from idanb import react, ui
from idanb.core.logs import logpath


@react.component
def NavigationBar() -> None:  # noqa: N802
    logs_open, set_logs_open = react.use_state(False)

    with mui.Box(
        className=f"{NavigationBar.__module__}.{NavigationBar.__qualname__}",
        sx=dict(
            position="fixed",
            top=0,
            right=0,
            display="grid",
            displayPrint="none",
            gridTemplateColumns="1fr",
            gridAutoFlow="column",
            gap=1,
            alignItems="center",
        ),
    ):
        with mui.Tooltip(
            title="Print",
            # Hide tooltip in print because it doesn't disappear fast enough.
            slotProps=dict(
                popper=dict(
                    sx=dict(displayPrint="none"),
                ),
            ),
        ):
            mui.IconButton(
                mui.icons.Print(),
                onClick=lambda: ui.print(),
                sx=dict(aspectRatio=1),
            )

        with mui.Tooltip(title="Logs"):
            mui.IconButton(
                mui.icons.Info(),
                onClick=lambda: set_logs_open(True),
                sx=dict(aspectRatio=1),
            )

        ui.FileContentsDialog(
            path=logpath(),
            open=logs_open,
            on_close=lambda: set_logs_open(False),
        )

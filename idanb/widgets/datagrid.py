from __future__ import annotations

import logging
from pathlib import Path

import typing_extensions as T
import perspective
import perspective.widget
import traitlets
from anywidget._file_contents import FileContents

from idanb import meta

if T.TYPE_CHECKING:
    import polars as pl


_logger = logging.getLogger(__name__)


# https://docs.rs/perspective-client/4.2.0/perspective_client/config/struct.ViewConfigUpdate.html
class DatagridConfig(T.TypedDict, total=False):
    """Configuration for datagrid front-end.

    ```py
    DatagridConfig(
        group_by=["CITY"],
        split_by=["BRANCH"],
        columns=["REVENUE", "EXPENSES", "PROFIT", "COUNT"],
        filter=[("PROFIT", ">", 0), ("BRANCH", "is not null", None)],
        sort=[("REVENUE", "desc")],
        expressions={"PROFIT": '"REVENUE" - "EXPENSES"', "COUNT": '"CITY"'},
        aggregates={"COUNT": "count"},
    )
    ```
    """

    group_by: T.Sequence[str]
    split_by: T.Sequence[str]
    columns: T.Sequence[str]
    filter: T.Sequence[tuple[str, str, T.Any]]
    sort: T.Sequence[tuple[str, str]]
    expressions: T.Mapping[str, str]
    aggregates: T.Mapping[str, str]
    group_by_depth: int
    filter_op: T.Literal["And", "Or"]


def _get_perspective_widget_esm() -> Path:
    esm = perspective.widget.PerspectiveWidget._esm  # noqa: SLF001
    if isinstance(esm, FileContents):
        return esm._path  # noqa: SLF001
    return esm


class Datagrid(perspective.widget.PerspectiveWidget):
    _esm: Path = Path(__file__).with_suffix(".js")

    _perspective_widget_esm: traitlets.Unicode = traitlets.Unicode(
        default_value=meta.urlof(_get_perspective_widget_esm()),
    ).tag(sync=True)

    styles: traitlets.Dict[str, str] = traitlets.Dict(
        key_trait=traitlets.Unicode(),
        value_trait=traitlets.Unicode(),
    ).tag(sync=True)
    templates: traitlets.Dict[str, str] = traitlets.Dict(
        key_trait=traitlets.Unicode(),
        value_trait=traitlets.Unicode(),
    ).tag(sync=True)

    def __init__(
        self,
        data: pl.DataFrame | None,
        *,
        styles: T.Mapping[str, str] | None = None,
        templates: T.Mapping[str, str] | None = None,
        **config: T.Unpack[DatagridConfig],
    ) -> None:
        self.styles = dict(styles or {})
        self.templates = dict(templates or {})
        super().__init__(data, **config)


# %run datagrid.ipy

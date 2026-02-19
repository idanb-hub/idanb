```python
from __future__ import annotations

from idanb.nbinit import logger
```

```python
import contextlib
import functools
import ipaddress
import itertools
import re
import textwrap
import typing
import uuid
from datetime import UTC, datetime, timedelta

import reacton
from ipymui import JavaScript, callback
from ipymui.components import mui

from idanb import meta, ui, utils
from idanb.core import queries
from idanb.infra.data_platform import DataPlatform, QueryProgress

if typing.TYPE_CHECKING:
    import typing_extensions as T
```

```python
dp = DataPlatform()
```

```python
def where_ip(ip: str, *, column: str) -> queries.Query:
    # Try parsing target as IP address.
    with contextlib.suppress(ValueError):
        ip = str(ipaddress.ip_address(ip))
        return queries.Query("{:SQL} = cast({} AS IPADDRESS)", column, ip)

    # Try parsing target is IP network (CIDR notation).
    with contextlib.suppress(ValueError):
        net = str(ipaddress.ip_network(ip, strict=False))
        return queries.Query("contains({}, {:SQL})", net, column)

    errmsg = f"{ip!r} is neither IP address nor network"
    raise ValueError(errmsg)


@utils.functional.then(queries.Query.join, delim="OR")
def where_src_target(targets: str) -> T.Iterable[queries.Query]:
    for target in targets.split():
        yield where_ip(
            target,
            column="coalesce(iana__sourceipv4address, iana__sourceipv6address)",
        )


@utils.functional.then(queries.Query.join, delim="OR")
def where_dst_target(targets: str) -> T.Iterable[queries.Query]:
    for target in targets.split():
        try:
            yield where_ip(
                target,
                column="coalesce(iana__destinationipv4address, iana__destinationipv6address)",
            )
        except ValueError:
            yield queries.Query(
                "(proto__http__host_http LIKE {0} OR proto__tls__sni_tls LIKE {0} OR proto__dns__qname_dns LIKE {0})",
                target,
            )


class NumbersExpression(utils.parse.RegexEnum):
    RANGE = r"\d+-\d+"
    NUMBER = r"\d+"
    NAME = r"\w+"


@utils.functional.then(queries.Query.join, delim="OR")
def where_numbers(
    values: str,
    *,
    what: str,
    column: str,
    names: T.Mapping[str, T.SupportsInt],
) -> T.Iterable[queries.Query]:
    for value in values.split():
        match = re.fullmatch(NumbersExpression.re, value)

        if match is None:
            errmsg = f"invalid {what}: {value!r}"
            raise ValueError(errmsg)

        assert match.lastgroup is not None, "regex is only groups"

        match NumbersExpression[match.lastgroup]:
            case NumbersExpression.RANGE:
                lo, hi = map(int, match[0].split("-"))
                yield queries.Query("{:SQL} BETWEEN {} AND {}", column, lo, hi)
            case NumbersExpression.NUMBER:
                yield queries.Query("{:SQL} = {}", column, int(match[0]))
            case NumbersExpression.NAME:
                name = match[0]
                found = names.get(name)
                if found is None:
                    errmsg = f"invalid {what} name: {name!r}"
                    raise ValueError(errmsg)
                yield queries.Query("{:SQL} = {}", column, int(found))


_where_ports = functools.partial(
    where_numbers,
    what="port",
    names=queries.data.PORTS,  # pyright: ignore[reportArgumentType]
)

where_src_port = functools.partial(
    _where_ports,
    column="iana__sourcetransportport",
)
where_dst_port = functools.partial(
    _where_ports,
    column="iana__destinationtransportport",
)

where_protocol = functools.partial(
    where_numbers,
    what="protocol",
    column="iana__protocolidentifier",
    names=queries.data.IP_PROTOCOLS,  # pyright: ignore[reportArgumentType]
)
```

```python
class QueryState(typing.TypedDict):
    src_addr: queries.Query
    dst_addr: queries.Query
    src_port: queries.Query
    dst_port: queries.Query
    mirror: bool
    start_time: datetime
    end_time: datetime
    protocols: queries.Query
    probes: list[str]
    view: str
    geoip: bool
    limit: int
    custom_condition: str


def make_query(state: QueryState) -> queries.Query:
    conditions = [
        # Mirrored conditions first.
        state["src_addr"],
        state["src_port"],
        state["dst_addr"],
        state["dst_port"],
    ]

    if state["mirror"]:
        conditions = [
            queries.Query.any(
                [
                    queries.Query.all(conditions),
                    queries.Query.all(conditions).transform(
                        utils.parse.substr_swap,
                        left="iana__source",
                        right="iana__destination",
                    ),
                ]
            ),
        ]

    # Now add non-mirrorred conditions.
    conditions.extend(
        [
            state["protocols"],
        ]
    )

    return queries.Query(
        textwrap.dedent("""\
        SELECT
        {columns:SQL}
        FROM ipfix
        LEFT JOIN geoip_country_locations as geoip_src
            ON cast(geoip_src.geoname_id AS VARCHAR) = ipfix.correlation00
        LEFT JOIN geoip_country_locations as geoip_dst
            ON cast(geoip_dst.geoname_id AS VARCHAR) = ipfix.correlation01
        WHERE
          (ts BETWEEN {time_start} AND {time_end})
          AND ({conditions:SQL})  -- conditions
          AND contains(transform({probes}, ip -> cast(ip AS IPADDRESS)), ipfix__srcaddr)
          AND ({where_custom:SQL})  -- custom
        LIMIT {limit}
        """),
        columns=textwrap.indent(
            queries.view(state["view"], geoip=state["geoip"]),
            "  ",
        ),
        time_start=state["start_time"].astimezone(UTC),
        time_end=state["end_time"].astimezone(UTC),
        conditions=queries.Query.all(conditions),
        probes=list(
            itertools.chain.from_iterable(
                queries.data.PROBES[probe] for probe in state["probes"]
            ),
        ),
        where_custom=state["custom_condition"] or "TRUE",
        limit=state["limit"],
    )
```

```python
table = ui.widgets.PerspectiveWidget(data=None)


@reacton.component
def QueryForm() -> None:  # noqa: N802 C901 PLR0915
    now = reacton.use_memo(lambda: datetime.now().astimezone())
    state, set_state = reacton.use_state(
        QueryState(
            src_addr=queries.Query(""),
            dst_addr=queries.Query(""),
            src_port=queries.Query(""),
            dst_port=queries.Query(""),
            mirror=False,
            end_time=now,
            start_time=(now - timedelta(minutes=5)),
            protocols=queries.Query(""),
            probes=[next(iter(queries.data.PROBES))],
            view="basic",
            geoip=True,
            limit=10000,
            custom_condition="",
        ),
    )

    with mui.Grid(
        container=True,
        spacing=1,
        # Otherwise things get cut off.
        padding=1,
    ):
        with mui.Grid(size=7):
            ui.ParsedField(
                label="Source address",
                value=state["src_addr"],
                on_value=lambda value: set_state({**state, "src_addr": value}),
                parser=where_src_target,
                init_value="",
                fullWidth=True,
            )

        with mui.Grid(size=5):
            ui.ParsedField(
                label="Source port",
                value=state["src_port"],
                on_value=lambda value: set_state({**state, "src_port": value}),
                parser=where_src_port,
                init_value="",
                fullWidth=True,
            )

        with mui.Grid(size=7):
            ui.ParsedField(
                label="Destination address",
                value=state["dst_addr"],
                on_value=lambda value: set_state({**state, "dst_addr": value}),
                parser=where_dst_target,
                init_value="",
                fullWidth=True,
            )

        with mui.Grid(size=5):
            ui.ParsedField(
                label="Destination port",
                value=state["dst_port"],
                on_value=lambda value: set_state({**state, "dst_port": value}),
                parser=where_dst_port,
                init_value="",
                fullWidth=True,
            )

        with mui.Grid(size=12):
            mui.FormControlLabel(
                label="Include flows in opposite direction",
                control=mui.Switch(
                    checked=state["mirror"],
                    onChange=callback("$[0].target.checked")(
                        lambda v: set_state({**state, "mirror": v}),
                    ),
                ),
            )

        mui.Grid(size=12, sx=dict(margin=1))

        with mui.Grid(size=3):
            ui.ParsedField(
                label="Protocols",
                value=state["protocols"],
                on_value=lambda value: set_state({**state, "protocols": value}),
                parser=where_protocol,
                init_value="tcp udp",
                fullWidth=True,
            )

        with mui.Grid(size=3), mui.FormControl(fullWidth=True):
            mui.InputLabel("Probes")
            with mui.Select(
                label="Probes",
                multiple=True,
                value=state["probes"],
                onChange=callback("$[0].target.value")(
                    lambda v: set_state({**state, "probes": v}),
                ),
            ):
                for probe in queries.data.PROBES:
                    mui.MenuItem(probe, value=probe)

        with mui.Grid(size=3):
            mui.date_pickers.DateTimePicker(
                label="Start time",
                value=state["start_time"],
                onChange=lambda value: set_state(
                    {**state, "start_time": datetime.fromisoformat(value)},
                ),
                sx=dict(width="100%"),
            )

        with mui.Grid(size=3):
            mui.date_pickers.DateTimePicker(
                label="Start time",
                value=state["end_time"],
                onChange=lambda value: set_state(
                    {**state, "end_time": datetime.fromisoformat(value)},
                ),
                sx=dict(width="100%"),
            )

        with mui.Grid(size=12):
            mui.TextField(
                label="Custom Condition",
                rows=1,
                multiline=True,
                onBlur=callback("$[0].target.value")(
                    lambda v: set_state({**state, "custom_condition": v}),
                ),
                fullWidth=True,
            )

        mui.Grid(size=12, sx=dict(margin=1))

        with mui.Grid(size=3), mui.FormControl(fullWidth=True):
            mui.InputLabel("View")
            with mui.Select(
                label="View",
                value=state["view"],
                onChange=callback("$[0].target.value")(
                    lambda value: set_state({**state, "view": value}),
                ),
                sx=dict(
                    flex=1,
                ),
            ):
                for view in queries.views():
                    mui.MenuItem(view, value=view)

        with mui.Grid(size=3, alignSelf="center"):
            mui.FormControlLabel(
                label="GeoIP",
                control=mui.Switch(
                    checked=state["geoip"],
                    onChange=callback("$[0].target.checked")(
                        lambda v: set_state({**state, "geoip": v}),
                    ),
                ),
            )

        with mui.Grid(size=3):
            mui.TextField(
                label="Limit",
                type="number",
                value=state["limit"],
                onChange=callback("$[0].target.value")(
                    lambda v: set_state({**state, "limit": v}),
                ),
                sx=dict(
                    flex=1,
                ),
            )

        query = make_query(state)

        progress, set_progress = reacton.use_state(
            typing.cast("QueryProgress | None", None)
        )

        @ui.use_task()
        async def get_flows() -> None:
            try:
                set_progress(None)
                logger.info("executing query", query=query)
                flows = await dp.execute(
                    *query,
                    on_progress=lambda p: set_progress(p),
                )
                table.load(flows)
            finally:
                set_progress(None)

        mui.Grid(size=12, sx=dict(margin=1))

        menu_open, set_menu_open = reacton.use_state(False)
        query_open, set_query_open = reacton.use_state(False)

        with mui.Grid(size="grow"):
            mui.Button(
                "Get Flows" if not get_flows.pending else "Cancel",
                onClick=lambda: (
                    get_flows() if not get_flows.pending else get_flows.cancel()
                ),
                variant="contained",
                fullWidth=True,
                size="large",
                color="primary" if not get_flows.pending else "error",
            )

        with mui.Grid(size="auto", alignSelf="center"):
            anchor_id = reacton.use_memo(lambda: f"x{uuid.uuid4().hex}")

            with mui.IconButton(
                variant="contained",
                id=anchor_id,
                onClick=lambda: set_menu_open(True),
            ):
                mui.icons.MoreVert()

            with mui.Menu(
                open=menu_open,
                anchorEl=JavaScript(f"document.querySelector('#{anchor_id}')"),
                onClose=lambda: set_menu_open(False),
            ):
                mui.MenuItem(
                    "Show SQL Query",
                    onClick=lambda: (
                        set_query_open(True),
                        set_menu_open(False),
                    ),
                )

            with mui.Dialog(
                open=query_open,
                onClose=lambda: set_query_open(False),
                fullWidth=True,
                maxWidth=False,
            ):
                mui.DialogTitle("SQL Query")
                with mui.DialogContent():
                    mui.Typography(
                        "\n".join(map(str, query)),
                        variant="body2",
                        sx=dict(
                            fontFamily="monospace",
                            whiteSpace="pre-wrap",
                        ),
                    )
                with mui.DialogActions():
                    mui.Button("Close", onClick=lambda: set_query_open(False))

    match get_flows.status:
        case get_flows.NotCalled():
            pass
        case get_flows.Pending():
            if progress is None:
                mui.LinearProgress()
                mui.Typography("SUBMITTING")
            else:
                mui.LinearProgress(
                    variant="determinate",
                    value=progress.progress,
                )
                mui.Link(
                    f"{progress.state}: {int(progress.progress)} %",
                    href=progress.url,
                    underline="none",
                )
        case get_flows.Exception(exception):
            mui.Alert(str(exception), severity="error")
        case get_flows.Result():
            display(table)
        case get_flows.Cancelled():
            if table.table is not None:
                display(table)


QueryForm()
```

```python
from idanb.core.observable_analysis import IntelOwl_ObservableAnalysis
from idanb.core.observable_analysis.analyzers import ALL_ANALYZERS

IntelOwl_ObservableAnalysis(analyzers=ALL_ANALYZERS)
```

```python
from idanb.core.save_table import SaveTablePage

SaveTablePage(
    table,
    savedir=meta.rootdir() / "data",
    savename=f"{__name__.split('.')[-1]}.csv",
)
```

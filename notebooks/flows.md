```python
from __future__ import annotations

from idanb.nbinit import logger, nbinit, rootdir

nbinit()
```

```python
import asyncio
import contextlib
import functools
import ipaddress
import itertools
import re
import textwrap
import typing
from datetime import UTC, datetime, timedelta

import solara
import solara.lab

from idanb import components, utils, widgets
from idanb.infrastructure.data_platform import DataPlatform, QueryProgress
from idanb.nbcommon import queries

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
@typing.final
class QueryStore:
    def __init__(self) -> None:
        self.src_addr = solara.reactive(queries.Query(""))
        self.dst_addr = solara.reactive(queries.Query(""))
        self.src_port = solara.reactive(queries.Query(""))
        self.dst_port = solara.reactive(queries.Query(""))
        self.mirror = solara.reactive(False)

        self.end_time = solara.reactive(datetime.now().astimezone())
        self.start_time = solara.reactive(
            self.end_time.peek() - timedelta(minutes=5)
        )

        self.protocols = solara.reactive(queries.Query(""))
        self.probes = solara.reactive(list(queries.data.PROBES.keys())[:1])

        self.view = solara.reactive("basic")
        self.geoip = solara.reactive(True)

        self.limit: solara.Reactive[int] = solara.reactive(10000)

        self.custom_condition = solara.reactive("")

        self.query = solara.lab.computed(self._query)

    def _query(self) -> queries.Query:
        conditions = [
            # Mirrored conditions first.
            self.src_addr.get(),
            self.src_port.get(),
            self.dst_addr.get(),
            self.dst_port.get(),
        ]

        if self.mirror.get():
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
                self.protocols.get(),
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
                queries.view(self.view.get(), geoip=self.geoip.get()),
                "  ",
            ),
            time_start=self.start_time.get().astimezone(UTC),
            time_end=self.end_time.get().astimezone(UTC),
            conditions=queries.Query.all(conditions),
            probes=list(
                itertools.chain.from_iterable(
                    queries.data.PROBES[probe] for probe in self.probes.get()
                ),
            ),
            where_custom=self.custom_condition.get() or "TRUE",
            limit=self.limit.get(),
        )
```

```python
table = widgets.PerspectiveWidget(data=None)


@solara.component
def QueryForm() -> None:  # noqa: N802
    store = solara.use_memo(lambda: QueryStore())

    with solara.Column(gap="0px"):
        with solara.Row():
            components.InputParsed(
                label="Source address",
                value=store.src_addr,
                parser=where_src_target,
                init="",
                style="flex: 3",
            )

            components.InputParsed(
                label="Source port",
                value=store.src_port,
                parser=where_src_port,
                init="",
                style="flex: 2",
            )

        with solara.Row():
            components.InputParsed(
                label="Destination address",
                value=store.dst_addr,
                parser=where_dst_target,
                init="",
                style="flex: 3",
            )

            components.InputParsed(
                label="Destination port",
                value=store.dst_port,
                parser=where_dst_port,
                init="",
                style="flex: 2",
            )

        with solara.Row():
            solara.Switch(
                label="Include flows in opposite direction",
                value=store.mirror,
            )

        with solara.Row():
            components.InputParsed(
                label="Protocols",
                value=store.protocols,
                parser=where_protocol,
                init="tcp udp",
            )
            solara.SelectMultiple(
                label="Probes",
                values=store.probes,  # pyright: ignore[reportArgumentType]
                all_values=list(queries.data.PROBES.keys()),
                on_value=lambda _: None,  # default conflicts with type annotations
                style="width: 20em",
            )
            components.InputDateTime(
                value=store.start_time,
                label="Start time",
                style="max-width: 20em",
            )
            components.InputDateTime(
                value=store.end_time,
                label="End time",
                style="max-width: 20em",
            )

        solara.InputTextArea(
            label="Custom Condition",
            value=store.custom_condition,
            rows=1,
        )

        with solara.Row():
            solara.Select(
                label="View",
                value=store.view,
                values=list(queries.views()),
                style="flex: 1",
            )
            solara.Switch(
                label="GeoIP",
                value=store.geoip,
                style="flex: 1",
            )
            solara.InputInt(
                label="Limit",
                value=store.limit,
                style="flex: 1",
            )

        progress: solara.Reactive[QueryProgress | None] = solara.use_reactive(
            None
        )

        @solara.lab.use_task(dependencies=None, raise_error=False)
        async def get_flows() -> None:
            try:
                progress.set(None)
                logger.info("executing query", query=store.query.get())
                flows = await dp.execute(
                    *store.query.get(),
                    on_progress=lambda p: progress.set(p),
                )
                table.load(flows)
            except asyncio.CancelledError:
                pass
            finally:
                progress.set(None)

        components.TaskButton(
            task=get_flows,
            label="Get Flows",
            color="primary",
            if_pending={
                "label": "Cancel",
                "color": "error",
            },
        )

        with solara.Details("SQL Query"):
            solara.Text(
                "\n".join(map(str, store.query.get())),
                style="font-family: monospace; white-space: pre-wrap;",
            )

        if get_flows.exception is not None:
            solara.Error(str(get_flows.exception))
        elif (p := progress.get()) is not None:
            solara.ProgressLinear(p.progress)
            components.Link(f"{p.state}: {int(p.progress)} %", url=p.url)
        elif get_flows.pending:
            solara.ProgressLinear(value=True)
            solara.Text("SUBMITTING")

        if get_flows.finished:
            solara.display(table)


QueryForm()
```

```python
from idanb.nbcommon.observable_analysis import IntelOwl_ObservableAnalysis
from idanb.nbcommon.observable_analysis.analyzers import ALL_ANALYZERS

IntelOwl_ObservableAnalysis(analyzers=ALL_ANALYZERS)
```

```python
from idanb.nbcommon.save_table import SaveTablePage

SaveTablePage(
    table,
    savedir=rootdir / "data",
    savename=f"{__name__.split('.')[-1]}.csv",
)
```

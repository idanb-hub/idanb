# Observable Analysis

Notebook for evaluation and analysis of an observable (hash, domain, or IP address)
using VirusTotal and for search of associated IOCs in network flow data.

<details>
<summary>Maintainers</summary>

- **Rudolf Lukac** ([lukac@ics.muni.cz](mailto:lukac@ics.muni.cz))

</details>

```python
from __future__ import annotations

from idanb.nbinit import logger
```

```python
import asyncio
import base64
import dataclasses
import socket
import textwrap
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import typing_extensions as T
import ipymui
from ipymui import callback
from ipymui.components import mui

import pydantic.dataclasses

from analytics.connectors.http import HTTPConnector
from idanb import meta, react, ui, utils
from idanb.meta import CONFIG

from new_connectors.sqlite_db import SQLiteConnector
```

```python
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VT_BASE_URL = "https://www.virustotal.com/api/v3/"


@CONFIG.register("virustotal")
@pydantic.dataclasses.dataclass()
class VirusTotalConfig:
    api_key: str


@CONFIG.register("sqlite_db")
@pydantic.dataclasses.dataclass()
class SQLiteDBConfig:
    path: str
```

```python
# ---------------------------------------------------------------------------
# VirusTotal helper: observable type detection and endpoint routing
# ---------------------------------------------------------------------------

def _is_url(observable: str) -> bool:
    return observable.startswith("https://") or observable.startswith("http://")


def _url_id(url: str) -> str:
    """VirusTotal URL identifier (base64url-encoded, no padding)."""
    return base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")


def _vt_endpoint(observable: str) -> str:
    """Return the VT API v3 path for the given observable."""
    if _is_url(observable):
        return f"urls/{_url_id(observable)}?relationships=comments"

    # IPv4 / IPv6 heuristic: contains '.' or ':'
    if "." in observable or ":" in observable:
        try:
            socket.inet_pton(socket.AF_INET, observable)
            return f"ip_addresses/{observable}?relationships=resolutions"
        except OSError:
            pass
        try:
            socket.inet_pton(socket.AF_INET6, observable)
            return f"ip_addresses/{observable}?relationships=resolutions"
        except OSError:
            pass
        # Otherwise treat as domain
        return f"domains/{observable}?relationships=resolutions"

    # No '.' or ':' → file hash
    return (
        f"files/{observable}"
        "?relationships=contacted_ips,contacted_domains,contacted_urls,"
        "bundled_files,dropped_files"
    )


def _gui_link(report: dict[str, T.Any]) -> str:
    return (
        report["data"]["links"]["self"]
        .replace("/api/v3/", "/gui/")
        .replace("/files/", "/file/")
        .replace("/ip_addresses/", "/ip-address/")
        .replace("/domains/", "/domain/")
        .replace("/urls/", "/url/")
    )
```

```python
# ---------------------------------------------------------------------------
# IOC data model
# ---------------------------------------------------------------------------

class IOCSet(utils.immutable.Record):
    """Extracted indicators of compromise from a VirusTotal report.

    Each entry is a tuple of (value, is_direct) where `is_direct` is True for
    IOCs pulled directly from the primary observable's report, and False for
    IOCs pulled from its associated (dropped / bundled) files.
    """

    ip_addresses: tuple[tuple[str, bool], ...] = ()
    domains: tuple[tuple[str, bool], ...] = ()
    urls: tuple[tuple[str, bool], ...] = ()

    def all_ips(self) -> list[str]:
        return [ip for ip, _ in self.ip_addresses]

    def all_domains(self) -> list[str]:
        return [d for d, _ in self.domains]

    def all_urls(self) -> list[str]:
        return [u for u, _ in self.urls]
```

```python
# ---------------------------------------------------------------------------
# IOC extraction logic (ported from old utilities)
# ---------------------------------------------------------------------------

def _extract_direct_iocs(
    observable: str,
    report: dict[str, T.Any],
) -> IOCSet:
    """Extract IOCs directly associated with the observable."""
    ips: list[tuple[str, bool]] = []
    domains: list[tuple[str, bool]] = []
    urls: list[tuple[str, bool]] = []

    obs_type = report["data"]["type"]
    rels = report["data"].get("relationships", {})

    # --- IPs ---
    if obs_type == "ip_address":
        ips.append((observable, True))
    if obs_type == "domain" and "resolutions" in rels:
        for item in rels["resolutions"]["data"]:
            # resolution id is "<ip><domain>", strip the trailing domain part
            ip = item["id"][: -len(observable)]
            if ip:
                ips.append((ip, True))
    if "contacted_ips" in rels:
        for item in rels["contacted_ips"]["data"]:
            ips.append((item["id"], True))

    # --- Domains ---
    if obs_type == "domain":
        domains.append((observable, True))
    if obs_type == "ip_address" and "resolutions" in rels:
        for item in rels["resolutions"]["data"]:
            # resolution id is "<ip><domain>", strip the leading IP part
            domain = item["id"][len(observable):]
            if domain:
                domains.append((domain, True))
    if "contacted_domains" in rels:
        for item in rels["contacted_domains"]["data"]:
            domains.append((item["id"], True))

    # --- URLs ---
    if obs_type == "url":
        urls.append((observable, True))
    if "contacted_urls" in rels:
        for item in rels["contacted_urls"]["data"]:
            urls.append((item["context_attributes"]["url"], True))

    return IOCSet(
        ip_addresses=tuple(ips),
        domains=tuple(domains),
        urls=tuple(urls),
    )


def _merge_iocs(base: IOCSet, extra: IOCSet) -> IOCSet:
    """Merge indirect IOCs into the accumulator, deduplicating against direct ones."""
    existing_ips = {v for v, _ in base.ip_addresses}
    existing_domains = {v for v, _ in base.domains}
    existing_urls = {v for v, _ in base.urls}

    new_ips = tuple(
        (v, False)
        for v, _ in extra.ip_addresses
        if v not in existing_ips
    )
    new_domains = tuple(
        (v, False)
        for v, _ in extra.domains
        if v not in existing_domains
    )
    new_urls = tuple(
        (v, False)
        for v, _ in extra.urls
        if v not in existing_urls
    )

    return IOCSet(
        ip_addresses=base.ip_addresses + new_ips,
        domains=base.domains + new_domains,
        urls=base.urls + new_urls,
    )
```

```python
# ---------------------------------------------------------------------------
# SQL views (ported from old_notebooks/utilities/static_data.py)
# ---------------------------------------------------------------------------

_SELECT_BASIC = textwrap.dedent("""\
    tslocal AS "START TIME - FIRST SEEN",
    CAST((iana__flowendmilliseconds - iana__flowstartmilliseconds) / 1000 AS INT) AS "DURATION",
    CASE iana__protocolidentifier
        WHEN 1  THEN 'ICMP'
        WHEN 6  THEN 'TCP'
        WHEN 17 THEN 'UDP'
        ELSE CAST(iana__protocolidentifier AS TEXT)
    END AS "PROTOCOL",
    COALESCE(iana__sourceipv4address, iana__sourceipv6address) AS "SOURCE IP ADDRESS",
    iana__sourcetransportport AS "SOURCE PORT",
    COALESCE(iana__destinationipv4address, iana__destinationipv6address) AS "DESTINATION IP ADDRESS",
    iana__destinationtransportport AS "DESTINATION PORT",
    iana__tcpcontrolbits__flags AS "TCP FLAGS",
    iana__packetdeltacount AS "PACKETS",
    iana__octetdeltacount AS "BYTES",
    UPPER(proto__detected_type) AS "DETECTED PROTOCOL",
    proto__http__host_http AS "HTTP HOST",
    proto__http__url_http AS "HTTP URL",
    proto__http__statuscode_http AS "HTTP STATUS CODE",
    proto__tls__sni_tls AS "TLS SNI",
    proto__dns__qname_dns AS "DNS QNAME",
    proto__dns__crrrdata_dns AS "DNS RESPONSE",
    CASE proto__dns__crrtype_dns
        WHEN 1     THEN 'A'
        WHEN 5     THEN 'CNAME'
        WHEN 28    THEN 'AAAA'
        WHEN 65    THEN 'HTTPS'
        WHEN 65535 THEN 'N/A'
        ELSE CAST(proto__dns__crrtype_dns AS TEXT)
    END AS "DNS RESPONSE TYPE",
    ipfix__srcaddr AS "PROBE"\
""")

_SELECT_GEOLOCATION = textwrap.dedent("""\
    tslocal AS "START TIME - FIRST SEEN",
    CAST((iana__flowendmilliseconds - iana__flowstartmilliseconds) / 1000 AS INT) AS "DURATION",
    CASE iana__protocolidentifier
        WHEN 1  THEN 'ICMP'
        WHEN 6  THEN 'TCP'
        WHEN 17 THEN 'UDP'
        ELSE CAST(iana__protocolidentifier AS TEXT)
    END AS "PROTOCOL",
    COALESCE(iana__sourceipv4address, iana__sourceipv6address) AS "SOURCE IP ADDRESS",
    geoip_src.country_iso_code || ', ' || geoip_src.country_name AS "SOURCE COUNTRY",
    iana__sourcetransportport AS "SOURCE PORT",
    COALESCE(iana__destinationipv4address, iana__destinationipv6address) AS "DESTINATION IP ADDRESS",
    geoip_dest.country_iso_code || ', ' || geoip_dest.country_name AS "DESTINATION COUNTRY",
    iana__destinationtransportport AS "DESTINATION PORT",
    iana__tcpcontrolbits__flags AS "TCP FLAGS",
    iana__packetdeltacount AS "PACKETS",
    iana__octetdeltacount AS "BYTES",
    UPPER(proto__detected_type) AS "DETECTED PROTOCOL",
    proto__http__host_http AS "HTTP HOST",
    proto__http__url_http AS "HTTP URL",
    proto__http__statuscode_http AS "HTTP STATUS CODE",
    proto__tls__sni_tls AS "TLS SNI",
    proto__dns__qname_dns AS "DNS QNAME",
    proto__dns__crrrdata_dns AS "DNS RESPONSE",
    CASE proto__dns__crrtype_dns
        WHEN 1     THEN 'A'
        WHEN 5     THEN 'CNAME'
        WHEN 28    THEN 'AAAA'
        WHEN 65    THEN 'HTTPS'
        WHEN 65535 THEN 'N/A'
        ELSE CAST(proto__dns__crrtype_dns AS TEXT)
    END AS "DNS RESPONSE TYPE",
    ipfix__srcaddr AS "PROBE"\
""")

_FROM_GEOLOCATION = textwrap.dedent("""\
    ipfix
    LEFT JOIN geoip_country_locations AS geoip_src
        ON CAST(geoip_src.geoname_id AS TEXT) = ipfix.correlation00
    LEFT JOIN geoip_country_locations AS geoip_dest
        ON CAST(geoip_dest.geoname_id AS TEXT) = ipfix.correlation01\
""")

DATA_VIEWS: dict[str, dict[str, str]] = {
    "basic": {
        "select": _SELECT_BASIC,
        "from": "ipfix",
    },
    "geolocation": {
        "select": _SELECT_GEOLOCATION,
        "from": _FROM_GEOLOCATION,
    },
}
```

```python
# ---------------------------------------------------------------------------
# IOC query builder (ported from old_notebooks/utilities/queries.py)
# ---------------------------------------------------------------------------

def _ip_clause(ips: list[str], src_col: str, dst_col: str) -> str:
    if not ips:
        return "FALSE"
    parts = []
    for ip in ips:
        col = dst_col if ":" in ip else src_col  # choose IPv6 col for v6 addrs
        # Use both source and destination columns
        parts.append(f"{src_col} = '{ip}'")
        parts.append(f"{dst_col} = '{ip}'")
    return " OR ".join(parts)


def _domain_clause(domains: list[str]) -> str:
    if not domains:
        return "FALSE"
    parts = []
    for d in domains:
        parts.append(
            f"proto__http__host_http LIKE '{d}'"
            f" OR proto__tls__sni_tls LIKE '{d}'"
            f" OR proto__dns__qname_dns LIKE '{d}'"
        )
    return " OR ".join(parts)


def _url_clause(urls: list[str]) -> str:
    if not urls:
        return "FALSE"
    parts = []
    for url in urls:
        parsed = urlparse(url)
        host = parsed.netloc
        path = parsed.path or "/"
        parts.append(
            f"(proto__http__host_http LIKE '{host}'"
            f" AND proto__http__url_http LIKE '{path}')"
        )
    return " OR ".join(parts)


def build_ioc_query(
    *,
    addresses: list[str],
    domains: list[str],
    urls: list[str],
    extra_addresses: list[str],
    extra_domains: list[str],
    start_time: datetime,
    end_time: datetime,
    view: str = "basic",
    limit: int | None = None,
) -> str:
    """Build a SQLite query to search for IOCs in network flows."""
    all_ips = addresses + extra_addresses
    all_domains = domains + extra_domains

    view_def = DATA_VIEWS[view]

    where_parts = [
        f"({_ip_clause(all_ips, 'iana__sourceipv4address', 'iana__destinationipv4address')})",
        f"({_ip_clause(all_ips, 'iana__sourceipv6address', 'iana__destinationipv6address')})",
        f"({_domain_clause(all_domains)})",
        f"({_url_clause(urls)})",
    ]
    where_iocs = " OR ".join(where_parts)

    limit_clause = f"LIMIT {limit}" if limit is not None else ""

    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S.%f%z")
    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S.%f%z")

    return textwrap.dedent(f"""\
        SELECT
            {view_def["select"]}
        FROM
            {view_def["from"]}
        WHERE (tslocal > '{start_str}' AND tslocal < '{end_str}')
            AND ({where_iocs})
        ORDER BY tslocal ASC
        {limit_clause}
    """)
```

```python
# ---------------------------------------------------------------------------
# Cross-section bridge state
# ---------------------------------------------------------------------------
import ipywidgets as _ipw

# Part 1 → Part 2: observable pushed from QuickAnalysis to ExtractIOCs.
_qa_observable: str = ""
_qa_obs_version = _ipw.IntText(value=0)


def _on_analyse_done(obs: str) -> None:
    global _qa_observable
    _qa_observable = obs
    _qa_obs_version.value += 1


# Part 2 → Part 3: IOCs pushed from ExtractIOCs to FlowSearch.
_extracted_iocs: IOCSet | None = None
_iocs_version = _ipw.IntText(value=0)


def _on_iocs(iocs: IOCSet) -> None:
    global _extracted_iocs
    _extracted_iocs = iocs
    _iocs_version.value += 1
```

## Quick Analysis

Analyses a provided observable (file hash, domain, or IP address) with VirusTotal
and displays basic results — number of malicious / undetected detections — with a
link to the full report.

```python
@react.component
def QuickAnalysis(  # noqa: N802
    *,
    on_report: T.Callable[[str, dict[str, T.Any]], None] | None = None,
    on_analyse_done: T.Callable[[str], None] | None = None,
) -> None:
    """Search an observable on VirusTotal and display a summary.

    Args:
        on_report: Called with (observable, report) when analysis succeeds.
            When provided, an "Extract IOCs" button is shown in the results.
    """
    if on_report is None:
        on_report = utils.functional.void

    observable, set_observable = react.use_state("")

    @react.use_task()
    async def analyse(obs: str) -> dict[str, T.Any]:
        vt_config = CONFIG[VirusTotalConfig]
        connector = HTTPConnector(mode="json")
        endpoint = _vt_endpoint(obs)
        report: dict[str, T.Any] = await connector.get(
            VT_BASE_URL + endpoint,
            headers={
                "accept": "application/json",
                "x-apikey": vt_config.api_key,
            },
        )
        await connector.close()
        return report

    def submit(formdata: dict[str, str]) -> None:
        obs = formdata["observable"].strip()
        set_observable(obs)
        analyse.start(obs)
        if on_analyse_done is not None:
            on_analyse_done(obs)

    with mui.Stack(spacing=1, sx=dict(my=1)):
        with mui.Stack(direction="row", spacing=1, alignItems="center"):
            with mui.Box(component="form", action=submit, sx=dict(flex=1)):
                mui.TextField(
                    label="Observable (hash / IP / domain / URL)",
                    name="observable",
                    defaultValue=observable,
                    key=observable,
                    fullWidth=True,
                    size="small",
                )
                mui.Button(
                    "Analyse",
                    type="submit",
                    variant="contained",
                    disabled=analyse.pending,
                    sx=dict(mt=1),
                )

        match analyse.status:
            case analyse.NotCalled():
                pass
            case analyse.Pending():
                mui.LinearProgress()
                mui.Typography("Querying VirusTotal…", variant="body2")
            case analyse.Exception(exc):
                mui.Alert(str(exc), severity="error")
            case analyse.Result(report):
                if "error" in report:
                    mui.Alert(
                        report["error"].get("message", "Unknown error"),
                        severity="error",
                    )
                else:
                    stats = report["data"]["attributes"]["last_analysis_stats"]
                    total = sum(stats.values())
                    malicious = stats.get("malicious", 0)
                    undetected = stats.get("undetected", 0)

                    with mui.Stack(spacing=1):
                        with mui.Stack(direction="row", spacing=2, alignItems="center"):
                            mui.Chip(
                                label=f"Malicious: {malicious}/{total}",
                                color="error" if malicious > 0 else "default",
                                variant="filled",
                            )
                            mui.Chip(
                                label=f"Undetected: {undetected}/{total}",
                                color="success",
                                variant="outlined",
                            )
                        mui.Link(
                            "Open full report on VirusTotal",
                            href=_gui_link(report),
                            target="_blank",
                            underline="hover",
                            variant="body2",
                        )
                        # Only shown when wired to ExtractIOCs via on_report.
                        if on_report is not utils.functional.void:
                            mui.Button(
                                "Extract IOCs",
                                variant="outlined",
                                size="small",
                                onClick=lambda: on_report(observable, report),
                                sx=dict(alignSelf="flex-start"),
                            )
QuickAnalysis(on_analyse_done=_on_analyse_done)
```

## Extract IOCs

Extracts IP addresses, domains, and URLs associated with the observable from its
VirusTotal report (direct IOCs which are highlighted with blue color in the report). 
Also checks any bundled or dropped files referenced in the report — if a related file is 
itself flagged as malicious (≥ 5 detections), its IOCs are included as indirect IOCs.

> **Note — passive DNS:** Extracted IP addresses and domains may include historical
> passive DNS resolutions, which can be outdated. Check the full VT report
> (`RELATIONS → Passive DNS Replication`) for resolution timestamps.

```python
@react.component
def ExtractIOCs(  # noqa: N802
    *,
    observable: str = "",
    report: dict[str, T.Any] | None = None,
    on_iocs: T.Callable[[IOCSet], None] | None = None,
) -> None:
    """Extract IOCs from a VirusTotal report.

    When called without arguments the component shows its own observable input
    and fetches the VT report internally (standalone mode). When `observable`
    and `report` are provided as props the fetch step is skipped.

    Args:
        observable: The observable that was analysed.
        report: Raw JSON report from the VT API.  When *None* the component
            fetches the report itself after the user submits the input form.
        on_iocs: Called with the extracted IOCSet when extraction completes.
            When provided, a "Use these IOCs" button is shown in the results.
    """
    if on_iocs is None:
        on_iocs = utils.functional.void

    # Track the observable the user typed in standalone mode.
    input_obs, set_input_obs = react.use_state(observable)

    # Guard: track the last IOCSet we already forwarded to Part 3 so we don't
    # re-fire on_iocs on every re-render.
    _last_iocs_sent, _set_last_iocs_sent = react.use_state(
        T.cast(IOCSet | None, None)
    )

    @react.use_task()
    async def extract(obs: str, rpt: dict[str, T.Any] | None) -> IOCSet:
        vt_config = CONFIG[VirusTotalConfig]
        connector = HTTPConnector(mode="json")
        headers = {
            "accept": "application/json",
            "x-apikey": vt_config.api_key,
        }

        # Standalone mode: fetch the VT report first.
        if rpt is None:
            rpt = await connector.get(
                VT_BASE_URL + _vt_endpoint(obs),
                headers=headers,
            )
            if "error" in rpt:
                await connector.close()
                raise RuntimeError(rpt["error"].get("message", "Unknown VT error"))

        iocs = _extract_direct_iocs(obs, rpt)

        # Enrich with IOCs from bundled/dropped files (indirect IOCs).
        rels = rpt["data"].get("relationships", {})
        related_files: list[str] = []
        for key in ("bundled_files", "dropped_files"):
            if key in rels:
                related_files.extend(item["id"] for item in rels[key]["data"])

        for file_hash in related_files:
            await asyncio.sleep(0.1)  # respect VT public API rate limit
            file_report: dict[str, T.Any] = await connector.get(
                VT_BASE_URL + f"files/{file_hash}"
                "?relationships=contacted_ips,contacted_domains,contacted_urls",
                headers=headers,
            )
            if "error" in file_report:
                continue
            malicious = file_report["data"]["attributes"][
                "last_analysis_stats"
            ].get("malicious", 0)
            if malicious < 5:  # noqa: PLR2004
                continue
            file_iocs = _extract_direct_iocs(file_hash, file_report)
            iocs = _merge_iocs(iocs, file_iocs)

        await connector.close()

        # Resolve IP addresses in a thread pool.
        all_ips = iocs.all_ips()

        async def resolve(ip: str) -> str:
            hostname = await asyncio.to_thread(socket.getfqdn, ip)
            return "" if hostname == ip else f"({hostname})"

        resolutions = await asyncio.gather(*[resolve(ip) for ip in all_ips])
        ips_with_res = tuple(
            (f"{ip} {res}".strip(), direct)
            for (ip, direct), res in zip(iocs.ip_addresses, resolutions)
        )

        return IOCSet(
            ip_addresses=ips_with_res,
            domains=iocs.domains,
            urls=iocs.urls,
        )


    def submit(formdata: dict[str, str]) -> None:
        obs = formdata["observable"].strip()
        set_input_obs(obs)
        extract.start(obs, None)  # fetch VT + extract in one shot

    # Standalone input form — shown only when no report is injected via props.
    if report is None:
        with mui.Box(component="form", action=submit, sx=dict(my=1)):
            mui.TextField(
                label="Observable (hash / IP / domain / URL)",
                name="observable",
                defaultValue=input_obs,
                key=input_obs,
                fullWidth=True,
                size="small",
            )
            mui.Button(
                "Extract IOCs",
                type="submit",
                variant="contained",
                disabled=extract.pending,
                sx=dict(mt=1),
            )

    # Wired mode: trigger extraction whenever a new report arrives via props.
    react.use_effect(
        lambda: extract.start(observable, report) if report is not None else None,
        [observable, report],
    )

    # Subscribe to Part 1 (QuickAnalysis) observable pushes — pre-fill the
    # input field whenever the user runs analysis in Part 1.
    def _subscribe_qa() -> T.Callable[[], None]:
        def _on_qa_change(change: dict) -> None:
            set_input_obs(_qa_observable)

        _qa_obs_version.observe(_on_qa_change, names=["value"])
        return lambda: _qa_obs_version.unobserve(_on_qa_change, names=["value"])

    react.use_effect(_subscribe_qa, [])

    match extract.status:
        case extract.NotCalled():
            pass
        case extract.Pending():
            mui.LinearProgress()
            mui.Typography("Extracting IOCs…", variant="body2")
        case extract.Exception(exc):
            mui.Alert(str(exc), severity="error")
        case extract.Result(iocs):
            # Auto-push ALL IOCs to Part 3 on first render of this result.
            # Guard: _last_iocs_sent prevents re-firing on every re-render.
            # Note: IOCSet is a Record (has __call__), so we must wrap in a
            # lambda to prevent reacton from treating it as a functional updater.
            if on_iocs is not utils.functional.void and iocs is not _last_iocs_sent:
                _set_last_iocs_sent(lambda _: iocs)
                on_iocs(iocs)

            def _chip_list(
                label: str,
                items: tuple[tuple[str, bool], ...],
            ) -> None:
                mui.Typography(label, variant="subtitle2")
                if not items:
                    mui.Typography("None", variant="body2", color="text.secondary")
                    return
                with mui.Box(sx=dict(display="flex", flexWrap="wrap", gap=0.5, mt=0.5)):
                    for value, is_direct in items:
                        mui.Chip(
                            label=value,
                            size="small",
                            color="primary" if is_direct else "default",
                            variant="filled",
                            title="Direct IOC" if is_direct else "Indirect IOC",
                        )

            with mui.Stack(spacing=1.5, sx=dict(my=1)):
                _chip_list("IP Addresses", iocs.ip_addresses)
                _chip_list("Domains", iocs.domains)
                _chip_list("URLs", iocs.urls)
```

```python
ExtractIOCs(on_iocs=_on_iocs)
```

## Search IOCs in Network Flows

Searches the extracted IOCs in a local database of network flows:

- **IP addresses** are matched against source and destination IP fields.
- **Domains** are matched in `DNS QNAME`, `TLS SNI`, and `HTTP HOST` fields.
- **URLs** are split into host + path, both must match in `HTTP HOST` / `HTTP URL`.

You can also add extra IP addresses and domains using the dedicated text fields.

```python
table = ui.widgets.PerspectiveWidget(data=None)
```

```python
class FlowSearchState(utils.immutable.Record):
    addresses: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    urls: tuple[str, ...] = ()
    extra_addresses: str = ""
    extra_domains: str = ""
    start_time: datetime = dataclasses.field(
        default_factory=lambda: datetime(2025, 2, 1, tzinfo=UTC),
    )
    end_time: datetime = dataclasses.field(
        default_factory=lambda: datetime(2025, 3, 1, tzinfo=UTC),
    )
    view: str = "basic"
    limit: int | None = 40000


@react.component
def FlowSearch(  # noqa: N802
    *,
    iocs: IOCSet | None = None,
) -> None:
    """Search IOCs in the SQLite flow database.

    Args:
        iocs: Pre-populated IOCs from the Extract IOCs step.
    """
    state, set_state = react.use_store(FlowSearchState())

    # Subscribe to cross-section IOC pushes from Part 2 (ExtractIOCs).
    # _iocs_version is a module-level ipywidgets.IntText; when its value
    # increments the observer fires set_ext_version, which triggers a re-render
    # so FlowSearch can read the freshly-stored _extracted_iocs.
    ext_version, set_ext_version = react.use_state(0)

    # Per-category IOC selection — auto-populated when new IOCs arrive.
    sel_ips, set_sel_ips = react.use_state(frozenset[str]())
    sel_domains, set_sel_domains = react.use_state(frozenset[str]())
    sel_urls, set_sel_urls = react.use_state(frozenset[str]())

    def _subscribe() -> T.Callable[[], None]:
        def _on_change(change: dict) -> None:
            set_ext_version(change["new"])

        _iocs_version.observe(_on_change, names=["value"])
        return lambda: _iocs_version.unobserve(_on_change, names=["value"])

    react.use_effect(_subscribe, [])

    # Pre-populate from IOCs whenever they arrive — either via the `iocs` prop
    # (wired mode) or via the shared counter (cross-section push from Part 2).
    effective_iocs = (_extracted_iocs if ext_version > 0 else None) or iocs

    # Clear selection whenever a new IOCSet arrives so the user picks
    # explicitly which IOCs to include in the search.
    react.use_effect(
        lambda: (
            set_sel_ips(frozenset()),
            set_sel_domains(frozenset()),
            set_sel_urls(frozenset()),
        )
        if effective_iocs is not None
        else None,
        [ext_version, iocs],
    )

    @react.use_task()
    async def search(
        s: FlowSearchState,
        addrs: tuple[str, ...],
        doms: tuple[str, ...],
        urls: tuple[str, ...],
    ) -> None:
        db_config = CONFIG[SQLiteDBConfig]
        connector = SQLiteConnector(path=db_config.path)

        extra_ips = [a.strip() for a in s.extra_addresses.split(",") if a.strip()]
        extra_domains = [d.strip() for d in s.extra_domains.split(",") if d.strip()]

        query = build_ioc_query(
            addresses=list(addrs),
            domains=list(doms),
            urls=list(urls),
            extra_addresses=extra_ips,
            extra_domains=extra_domains,
            start_time=s.start_time,
            end_time=s.end_time,
            view=s.view,
            limit=s.limit,
        )

        async with connector.execute(query) as q:
            rows = list(q._rows)
            columns = [col[0] for col in q.schema]

        import polars as pl

        df = pl.DataFrame(rows, schema=columns, orient="row")
        table.load(df)

    with mui.Stack(spacing=2, sx=dict(my=1)):
        # --- IOC selector (populated from Part 2 results) ---
        if effective_iocs is not None:
            def _selectable_chip_list(
                label: str,
                items: tuple[tuple[str, bool], ...],
                sel: frozenset[str],
                set_sel: T.Callable[[frozenset[str]], None],
            ) -> None:
                with mui.Stack(
                    direction="row",
                    spacing=1,
                    alignItems="center",
                    sx=dict(mb=0.5),
                ):
                    mui.Typography(label, variant="subtitle2")
                    if items:
                        mui.Typography(
                            f"({len(sel)}/{len(items)} selected)",
                            variant="caption",
                            color="text.secondary",
                        )
                        mui.Link(
                            "all",
                            onClick=lambda: set_sel(
                                frozenset(v for v, _ in items)
                            ),
                            variant="caption",
                            sx=dict(cursor="pointer"),
                        )
                        mui.Typography("·", variant="caption", color="text.disabled")
                        mui.Link(
                            "none",
                            onClick=lambda: set_sel(frozenset()),
                            variant="caption",
                            sx=dict(cursor="pointer"),
                        )
                if not items:
                    mui.Typography("None", variant="body2", color="text.secondary")
                    return
                with mui.Box(sx=dict(display="flex", flexWrap="wrap", gap=0.5)):
                    for value, is_direct in items:
                        selected = value in sel
                        toggle = (
                            lambda v: lambda: set_sel(
                                lambda s: s - {v} if v in s else s | {v}
                            )
                        )(value)

                        mui.Chip(
                            label=value,
                            size="small",
                            color="primary" if is_direct else "default",
                            variant="filled" if selected else "outlined",
                            title=(
                                ("Direct" if is_direct else "Indirect")
                                + " IOC — click to "
                                + ("deselect" if selected else "select")
                            ),
                            onClick=toggle,
                            clickable=True,
                        )

            with mui.Stack(spacing=1.5):
                _selectable_chip_list(
                    "IP Addresses",
                    effective_iocs.ip_addresses,
                    sel_ips,
                    set_sel_ips,
                )
                _selectable_chip_list(
                    "Domains",
                    effective_iocs.domains,
                    sel_domains,
                    set_sel_domains,
                )
                _selectable_chip_list(
                    "URLs",
                    effective_iocs.urls,
                    sel_urls,
                    set_sel_urls,
                )

        # --- Filters ---
        with mui.Grid(container=True, spacing=1):
            with mui.Grid(size=6):
                mui.TextField(
                    label="Extra IP Addresses (comma-separated)",
                    value=state.extra_addresses,
                    onChange=callback("$[0].target.value")(
                        lambda v: set_state(extra_addresses=v),
                    ),
                    fullWidth=True,
                    size="small",
                )

            with mui.Grid(size=6):
                mui.TextField(
                    label="Extra Domains (comma-separated)",
                    value=state.extra_domains,
                    onChange=callback("$[0].target.value")(
                        lambda v: set_state(extra_domains=v),
                    ),
                    fullWidth=True,
                    size="small",
                )

            with mui.Grid(size=4):
                mui.date_pickers.DateTimePicker(
                    label="Start time",
                    value=state.start_time,
                    onChange=lambda v: set_state(
                        start_time=datetime.fromisoformat(v),
                    ),
                    sx=dict(width="100%"),
                )

            with mui.Grid(size=4):
                mui.date_pickers.DateTimePicker(
                    label="End time",
                    value=state.end_time,
                    onChange=lambda v: set_state(
                        end_time=datetime.fromisoformat(v),
                    ),
                    sx=dict(width="100%"),
                )

            with mui.Grid(size=2), mui.FormControl(fullWidth=True, size="small"):
                mui.InputLabel("View")
                with mui.Select(
                    label="View",
                    value=state.view,
                    onChange=callback("$[0].target.value")(
                        lambda v: set_state(view=v),
                    ),
                ):
                    for name in DATA_VIEWS:
                        mui.MenuItem(name.capitalize(), value=name)

            with mui.Grid(size=2), mui.FormControl(fullWidth=True, size="small"):
                mui.InputLabel("Limit")
                with mui.Select(
                    label="Limit",
                    value=state.limit,
                    onChange=callback("$[0].target.value")(
                        lambda v: set_state(limit=int(v) if v else None),
                    ),
                ):
                    mui.MenuItem("No limit", value=None)
                    for n in (1000, 10000, 40000, 100000):
                        mui.MenuItem(str(n), value=n)

        # --- Submit ---
        n_sel = len(sel_ips) + len(sel_domains) + len(sel_urls)
        mui.Button(
            "Search Flows" if not search.pending else "Searching…",
            variant="contained",
            disabled=search.pending or n_sel == 0,
            onClick=lambda: search.start(
                state,
                tuple(v.split()[0] for v in sel_ips),
                tuple(sel_domains),
                tuple(sel_urls),
            ),
            fullWidth=True,
        )

        # --- Status / results ---
        match search.status:
            case search.NotCalled():
                pass
            case search.Pending():
                mui.LinearProgress()
            case search.Exception(exc):
                mui.Alert(str(exc), severity="error")
            case search.Result():
                display(table)  # noqa: F821
FlowSearch()
```

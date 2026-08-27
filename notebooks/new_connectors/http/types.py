from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    import asyncio
    from collections.abc import Awaitable, Callable, Iterable, Sequence

    import aiohttp
    import aiohttp.abc
    import aiohttp.typedefs
    from yarl import URL


class ClientSessionParams(typing.TypedDict, total=False):
    """Keyword arguments for `aiohttp.ClientSession`."""

    base_url: str | URL | None
    connector: aiohttp.BaseConnector | None
    loop: asyncio.AbstractEventLoop | None
    cookies: aiohttp.typedefs.LooseCookies | None
    headers: aiohttp.typedefs.LooseHeaders | None
    proxy: str | URL | None
    proxy_auth: aiohttp.BasicAuth | None
    skip_auto_headers: Iterable[str] | None
    auth: aiohttp.BasicAuth | None
    json_serialize: aiohttp.typedefs.JSONEncoder
    request_class: type[aiohttp.ClientRequest]
    response_class: type[aiohttp.ClientResponse]
    ws_response_class: type[aiohttp.ClientWebSocketResponse]
    version: aiohttp.HttpVersion
    cookie_jar: aiohttp.abc.AbstractCookieJar | None
    connector_owner: bool
    raise_for_status: bool | Callable[[aiohttp.ClientResponse], Awaitable[None]]
    read_timeout: float
    conn_timeout: float | None
    timeout: object | aiohttp.ClientTimeout
    auto_decompress: bool
    trust_env: bool
    requote_redirect_url: bool
    trace_configs: list[aiohttp.TraceConfig] | None
    read_bufsize: int
    max_line_size: int
    max_field_size: int
    fallback_charset_resolver: Callable[[aiohttp.ClientResponse, bytes], str]
    middlewares: Sequence[aiohttp.ClientMiddlewareType]
    ssl_shutdown_timeout: None | float


if typing.TYPE_CHECKING:
    # Check that it works.
    _ = aiohttp.ClientSession(**ClientSessionParams())

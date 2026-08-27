from __future__ import annotations

import asyncio
import contextlib
import typing

from new_connectors import _common as common

import aiohttp

if typing.TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Generator

    from aiohttp.client import _RequestOptions as RequestParams
    from yarl import URL

    from .config import HTTPConfig
    from .types import ClientSessionParams


class HTTPResponse[Payload](aiohttp.ClientResponse):
    _receiving: bool = False

    def __await__(self) -> Generator[typing.Any, typing.Any, Payload]:
        raise NotImplementedError

    def __init_subclass__[Result](
        cls: type[HTTPResponse[Result]],
        awaiter: Callable[[aiohttp.ClientResponse], Awaitable[Result]],
        **kwargs: object,
    ) -> None:
        cls.__await__ = lambda self: awaiter(self).__await__()
        return super().__init_subclass__(**kwargs)

    async def receive(
        self,
        *,
        chunk_size: int = 4096,
        save: bool = True,
    ) -> AsyncIterator[tuple[int, bytes]]:
        """Stream response content.

        Args:
            chunk_size: Maximum size of yielded chunks.
            save: Whether to store content (turn off to save memory).

        Yields:
            Tuple of "number of bytes read so far" and "latest chunk received".
        """
        self._receiving = True
        try:
            chunks: list[bytes] = []
            total_size = 0

            async for chunk in self.content.iter_chunked(chunk_size):
                chunks.append(chunk)
                total_size += len(chunk)
                yield total_size, chunk

            if save:
                # Same is done in `self.read()`.
                self._body: bytes | None = b"".join(chunks)
        finally:
            self._receiving = False

    @typing.override
    async def read(self) -> bytes:
        if self._receiving:
            errmsg = "Cannot read body until receive iterator is exhausted"
            raise RuntimeError(errmsg)
        return await super().read()


class HTTPConnector[Payload]:
    session: aiohttp.ClientSession

    _semaphore: contextlib.AbstractAsyncContextManager[None]

    @typing.overload
    def __init__(
        self: HTTPConnector[str],
        config: HTTPConfig | None = ...,
        /,
        *,
        mode: typing.Literal["text"] = ...,
        concurrency_limit: int | None = None,
        **options: typing.Unpack[ClientSessionParams],
    ) -> None: ...

    @typing.overload
    def __init__(
        self: HTTPConnector[bytes],
        config: HTTPConfig | None = ...,
        /,
        *,
        mode: typing.Literal["bytes"],
        concurrency_limit: int | None = None,
        **options: typing.Unpack[ClientSessionParams],
    ) -> None: ...

    @typing.overload
    def __init__(
        self: HTTPConnector[object],
        config: HTTPConfig | None = ...,
        /,
        *,
        mode: typing.Literal["json"],
        concurrency_limit: int | None = None,
        **options: typing.Unpack[ClientSessionParams],
    ) -> None: ...

    def __init__(
        self,
        config: HTTPConfig | None = None,
        /,
        *,
        mode: typing.Literal["text", "bytes", "json"] = "text",
        concurrency_limit: int | None = None,
        **options: typing.Unpack[ClientSessionParams],
    ) -> None:
        """Create an HTTP client session.

        Args:
            config: Session configuration.
            mode: Default response payload format.
            concurrency_limit: Maximum number of concurrent requests.
            options: Extra options for `aiohttp.ClientSession` (overrides ones
                from `config`).
        """
        if config is not None:
            options.setdefault(
                "timeout",
                aiohttp.ClientTimeout(total=config.timeout),
            )
            if concurrency_limit is None:
                concurrency_limit = config.concurrency_limit

        self._semaphore = (
            asyncio.Semaphore(concurrency_limit)
            if concurrency_limit
            else contextlib.nullcontext()
        )

        response_class = options.pop("response_class", aiohttp.ClientResponse)

        match mode:
            case "text":
                awaiter = response_class.text
            case "bytes":
                awaiter = response_class.read
            case "json":
                awaiter = response_class.json

        bases: list[type[aiohttp.ClientResponse]] = [HTTPResponse]
        if response_class is not aiohttp.ClientResponse:
            bases.insert(0, response_class)

        options["response_class"] = type(
            f"{mode.capitalize()}HTTPResponse",
            tuple(bases),
            {},
            awaiter=awaiter,
        )

        self.session = aiohttp.ClientSession(**options)

    async def close(self) -> None:
        await self.session.close()

    @common.queryfactory[Payload]()
    async def request(
        self,
        method: str,
        url: str | URL,
        **kwargs: typing.Unpack[RequestParams],
    ) -> AsyncIterator[HTTPResponse[Payload]]:
        """Perform an HTTP request and return its response.

        Can be awaited directly or used as an async context manager.

        If awaited directly, returns the response body (in its default format).

        ```py
        content = await connector.request("GET", "https://wttr.in")
        print(content)  # string because `mode` is "text"
        ```

        If used as an async context manager, behaves as `aiohttp.ClientResponse`
        (see its docs). It has an additional `.receive` method that yields
        progress as response is being received.

        ```py
        async with connector.request("GET", "https://wttr.in") as response:
            response.raise_for_status()
            async for length, chunk in response.receive():
                print(f"{length}/{response.content_length}")
            print(await response.text())
        ```
        """
        async with (
            self._semaphore,
            self.session.request(method, url, **kwargs) as response,
        ):
            yield typing.cast("HTTPResponse[Payload]", response)

    type Response = common.AwaitableContextManager[
        HTTPResponse[Payload],
        bool | None,
        Payload,
    ]

    def get(
        self,
        url: str | URL,
        **kwargs: typing.Unpack[RequestParams],
    ) -> Response:
        """Perform a GET request and return its response.

        Same as `self.request("GET", url, **kwargs)`.
        """
        return self.request(aiohttp.hdrs.METH_GET, url, **kwargs)

    def options(
        self,
        url: str | URL,
        **kwargs: typing.Unpack[RequestParams],
    ) -> Response:
        """Perform an OPTIONS request and return its response.

        Same as `self.request("OPTIONS", url, **kwargs)`.
        """
        return self.request(aiohttp.hdrs.METH_OPTIONS, url, **kwargs)

    def head(
        self,
        url: str | URL,
        **kwargs: typing.Unpack[RequestParams],
    ) -> Response:
        """Perform a HEAD request and return its response.

        Same as `self.request("HEAD", url, **kwargs)`.
        """
        return self.request(aiohttp.hdrs.METH_HEAD, url, **kwargs)

    def post(
        self,
        url: str | URL,
        **kwargs: typing.Unpack[RequestParams],
    ) -> Response:
        """Perform a POST request and return its response.

        Same as `self.request("POST", url, **kwargs)`.
        """
        return self.request(aiohttp.hdrs.METH_POST, url, **kwargs)

    def put(
        self,
        url: str | URL,
        **kwargs: typing.Unpack[RequestParams],
    ) -> Response:
        """Perform a PUT request and return its response.

        Same as `self.request("PUT", url, **kwargs)`.
        """
        return self.request(aiohttp.hdrs.METH_PUT, url, **kwargs)

    def patch(
        self,
        url: str | URL,
        **kwargs: typing.Unpack[RequestParams],
    ) -> Response:
        """Perform a PATCH request and return its response.

        Same as `self.request("PATCH", url, **kwargs)`.
        """
        return self.request(aiohttp.hdrs.METH_PATCH, url, **kwargs)

    def delete(
        self,
        url: str | URL,
        **kwargs: typing.Unpack[RequestParams],
    ) -> Response:
        """Perform a DELETE request and return its response.

        Same as `self.request("DELETE", url, **kwargs)`.
        """
        return self.request(aiohttp.hdrs.METH_DELETE, url, **kwargs)

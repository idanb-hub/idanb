from __future__ import annotations

import asyncio
import sqlite3
import typing

from new_connectors import _common as common

if typing.TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator
    from pathlib import Path

    from .config import SQLiteConfig


class SQLiteQuery:
    """Fully fetched query results."""

    _rows: list[tuple[object, ...]]
    _description: list[sqlite3.Column]

    def __init__(
        self,
        rows: list[tuple[object, ...]],
        description: list[sqlite3.Column],
    ) -> None:
        self._rows = rows
        self._description = description

    @property
    def schema(self) -> list[sqlite3.Column]:
        """Column descriptions returned by the query."""
        return self._description

    async def collect(self) -> Iterator[tuple[object, ...]]:
        """Return an iterator over all result rows."""
        return iter(self._rows)

    def __aiter__(self) -> AsyncIterator[tuple[object, ...]]:
        """Iterate over the result rows."""

        async def _iter() -> AsyncIterator[tuple[object, ...]]:
            for row in self._rows:
                yield row

        return _iter()


class SQLiteConnector:
    _path: str | Path

    def __init__(
        self,
        config: SQLiteConfig | None = None,
        /,
        *,
        path: str | Path | None = None,
    ) -> None:
        """Open a connection to a local SQLite database file.

        Args:
            config: Connection configuration.
            path: Path to the SQLite database file (overrides `config.path`).
        """
        if path is None:
            if config is None:
                errmsg = "either 'config' or 'path' must be provided"
                raise ValueError(errmsg)
            path = config.path
        self._path = path

    @common.queryfactory(SQLiteQuery.collect)
    async def execute(
        self,
        query: str,
        *params: object,
    ) -> AsyncIterator[SQLiteQuery]:
        """Execute a query and receive its results.

        Args:
            query: Query string ('?' for params).
            params: Query parameters (replace '?' in query).

        Can be awaited directly or used as an async context manager.

        If awaited directly, returns an iterator over result rows.

        ```py
        rows = await connector.execute("SELECT * FROM table LIMIT ?", 10)
        ```

        If used as an async context manager, the managed object exposes
        result rows and column metadata.

        ```py
        async with connector.execute("SELECT * FROM table") as query:
            print(query.schema)
            async for row in query: ...
        ```
        """

        def _run() -> SQLiteQuery:
            conn = sqlite3.connect(self._path)
            try:
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                description = list(cursor.description or [])
            finally:
                conn.close()
            return SQLiteQuery(rows, description)

        result = await asyncio.to_thread(_run)
        yield result

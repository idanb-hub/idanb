"""Filesystem utilities."""

from __future__ import annotations

import itertools
import types
from pathlib import Path

import typing_extensions as T
from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    FileClosedEvent,
    FileClosedNoWriteEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileOpenedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

if T.TYPE_CHECKING:
    from watchdog.observers.api import BaseObserver


class FileSystemEventCallbacks(T.TypedDict, total=False):
    on_event: T.Callable[[FileSystemEvent], None]
    on_moved: T.Callable[[DirMovedEvent | FileMovedEvent], None]
    on_created: T.Callable[[DirCreatedEvent | FileCreatedEvent], None]
    on_deleted: T.Callable[[DirDeletedEvent | FileDeletedEvent], None]
    on_modified: T.Callable[[DirModifiedEvent | FileModifiedEvent], None]
    on_closed: T.Callable[[FileClosedEvent], None]
    on_closed_no_write: T.Callable[[FileClosedNoWriteEvent], None]
    on_opened: T.Callable[[FileOpenedEvent], None]


class DelegateEventHandler(FileSystemEventHandler):
    def __init__(self, **callbacks: T.Unpack[FileSystemEventCallbacks]) -> None:
        for name, callback in callbacks.items():
            setattr(self, name, callback)

        super().__init__()


def watch(
    path: str | Path,
    *,
    recursive: bool = True,
    **callbacks: T.Unpack[FileSystemEventCallbacks],
) -> BaseObserver:
    """Watch `path` for filesystem events."""
    events: list[type[FileSystemEvent]] = []

    # Extract relevant event types from `FileSystemEventCallbacks`.
    hints = T.get_type_hints(FileSystemEventCallbacks)
    for callback in callbacks:
        hint = hints[callback]
        params, _ = T.get_args(hint)
        event = params[0]
        if isinstance(event, types.UnionType):
            events.extend(T.get_args(event))
        else:
            events.append(event)

    handler = DelegateEventHandler(**callbacks)
    observer = Observer()
    observer.schedule(
        handler,
        str(path),
        recursive=recursive,
        event_filter=events,
    )
    observer.start()
    return observer


def glob(
    include: str | T.Iterable[str],
    exclude: str | T.Iterable[str] = (),
    root: str | Path = ".",
) -> T.Collection[Path]:
    root = Path(root)
    if isinstance(include, str):
        include = [include]
    if isinstance(exclude, str):
        exclude = [exclude]

    included, excluded = (
        itertools.chain.from_iterable(map(root.glob, globs))
        for globs in (include, exclude)
    )

    result = set(included)
    result.difference_update(excluded)
    return result


class Entry(T.NamedTuple):
    path: Path
    entries: T.Iterable[Entry] | None


def walk(
    root: str | Path = ".",
    include: str | T.Iterable[str] = "*",
    exclude: str | T.Iterable[str] = (),
    *,
    lazy: bool = False,
) -> T.Iterable[Entry]:
    entries = _walk(root, include, exclude, lazy=lazy)
    if not lazy:
        entries = list(entries)
    return entries


def _walk(
    root: str | Path,
    include: str | T.Iterable[str],
    exclude: str | T.Iterable[str],
    *,
    lazy: bool,
) -> T.Iterable[Entry]:
    entries = glob(include, exclude, root)
    for entry in sorted(entries):
        if entry.is_dir():
            yield Entry(entry, walk(entry, include, exclude, lazy=lazy))
        else:
            yield Entry(entry, None)

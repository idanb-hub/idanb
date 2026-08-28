from __future__ import annotations

import dataclasses

import typing_extensions as T

if T.TYPE_CHECKING:
    from pathlib import Path


@dataclasses.dataclass()
class SQLiteConfig:
    path: str | Path

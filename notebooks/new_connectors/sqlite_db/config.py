from __future__ import annotations

import dataclasses
from pathlib import Path


@dataclasses.dataclass()
class SQLiteConfig:
    path: str | Path

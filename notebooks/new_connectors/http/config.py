from __future__ import annotations

import dataclasses


@dataclasses.dataclass()
class HTTPConfig:
    timeout: float = 30.0
    concurrency_limit: int = 0

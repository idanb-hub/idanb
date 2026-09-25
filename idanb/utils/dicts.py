from __future__ import annotations

import typing_extensions as T


def insert[K, V](
    mapping: T.Mapping[K, V],
    inserts: T.Mapping[K, T.Mapping[K, V]],
) -> dict[K, V]:
    """Create dictionary with additional items inserted after specific keys.

    >>> insert({1: 1, 3: 3}, {1: {2: 2}})
    {1: 1, 2: 2, 3: 3}
    """
    d: dict[K, V] = {}
    for k, v in mapping.items():
        d[k] = v
        insert = inserts.get(k, None)
        if insert is not None:
            d.update(insert)
    return d

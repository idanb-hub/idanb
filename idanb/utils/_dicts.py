from __future__ import annotations

import collections

import typing_extensions as T


class TransformDict[Key, Value](collections.UserDict[Key, Value]):
    """Dictionary that transforms keys using a provided function."""

    transform: T.Callable[[Key], Key]

    def __init__(
        self,
        transform: T.Callable[[Key], Key],
        init: T.Iterable[tuple[Key, Value]] | T.Mapping[Key, Value] = (),
        /,
        **kwargs: Value,
    ) -> None:
        self.transform = transform
        super().__init__(init, **kwargs)

    @T.override
    def __getitem__(self, key: Key) -> Value:
        return super().__getitem__(self.transform(key))

    @T.override
    def __setitem__(self, key: Key, item: Value) -> None:
        return super().__setitem__(self.transform(key), item)

    @T.override
    def __delitem__(self, key: Key) -> None:
        return super().__delitem__(self.transform(key))

    @T.override
    def __contains__(self, key: object) -> bool:
        try:
            transformed = self.transform(key)  # pyright: ignore[reportArgumentType]
        except TypeError:
            return False
        return super().__contains__(transformed)


class CaselessDict[Key, Value](TransformDict[Key, Value]):
    """Case insensitive dictionary. Keys are stored in lowercase."""

    def __init__(
        self,
        init: T.Iterable[tuple[Key, Value]] | T.Mapping[Key, Value] = (),
        /,
        **kwargs: Value,
    ) -> None:
        def transform(key: Key) -> Key:
            if isinstance(key, str | bytes):
                return T.cast("Key", key.lower())
            return key

        super().__init__(transform, init, **kwargs)

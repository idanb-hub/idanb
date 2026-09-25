from __future__ import annotations

import abc
import builtins
import dataclasses
import types
from collections.abc import Mapping, Sequence
from pathlib import Path

import typing_extensions as T

from ._typetools import is_mapping, is_sequence

if T.TYPE_CHECKING:
    from _typeshed import SupportsGetItem


class ConfigError(RuntimeError):
    message: str
    path: tuple[str | int, ...]

    def __init__(
        self,
        message: str,
        path: tuple[str | int, ...],
    ) -> None:
        self.message = message
        self.path = path
        super().__init__(message, path)

    @T.override
    def __str__(self) -> str:
        path = "".join(
            f".{p}" if isinstance(p, str) and p.isidentifier() else f"[{p!r}]"
            for p in self.path
        )
        return f"{self.message} (at {path or '.'})"


class ConfigTypeError(ConfigError):
    def __init__(
        self,
        expected: type,
        actual: type,
        path: tuple[str | int, ...],
    ) -> None:
        message = f"expected {expected.__name__}, found {actual.__name__}"
        super().__init__(message, path)


NO_DEFAULT = T.Sentinel("NO_DEFAULT")


class Config[Data]:
    _data: Data
    _paths: dict[type, tuple[str | int, ...]]
    _cache: dict[type, T.Any]
    _reload: T.Callable[[], Data | None] | None

    def __init__(
        self,
        data: Data,
        *,
        reload: T.Callable[[], Data | None] | None = None,
    ) -> None:
        """Create a new `Config` instance from `data`.

        If `reload` is not `None`, it is called whenever data is accessed
        and can return new data to use instead (or `None` to keep current data).
        """
        self._data = data
        self._paths = {}
        self._cache = {}
        self._reload = reload

    @property
    def data(self) -> Data:
        _ = self.reload()
        return self._data

    @data.setter
    def data(self, value: Data) -> None:
        self._data = value
        self._cache.clear()

    def reload(self) -> bool:
        if self._reload is None:
            return False

        data = self._reload()
        if data is None:
            return False

        self.data = data
        return True

    def register[Cls: type](self, *path: str | int) -> T.Callable[[Cls], Cls]:

        def decorator(cls: Cls) -> Cls:
            self._paths[cls] = path
            return cls

        return decorator

    @T.overload
    def __getitem__[Cls](self, cls: type[Cls], /) -> Cls: ...

    @T.overload
    def __getitem__(
        self,
        path: str | int | tuple[str | int, ...],
        /,
    ) -> object: ...

    def __getitem__[Cls](
        self,
        cls_or_path: type[Cls] | str | int | tuple[str | int, ...],
    ) -> object:
        if isinstance(cls_or_path, type):
            cls = cls_or_path
            return self._getinstance(cls, reload=True)

        path = cls_or_path
        if not isinstance(path, tuple):
            path = (path,)
        return self._getvalue(*path, reload=True)

    @T.overload
    def get[Type](
        self,
        *path: str | int,
        type: type[Type] = object,
    ) -> Type: ...

    @T.overload
    def get[Type, Default](
        self,
        *path: str | int,
        default: Default,
        type: type[Type] = object,
    ) -> Type | Default: ...

    def get[Type, Default](
        self,
        *path: str | int,
        type: type[Type] = object,
        default: Default = NO_DEFAULT,
    ) -> Type | Default:
        """Get value at specified `path`.

        >>> c = Config([0, {"key": "v"}])
        >>> c.get(0)
        0
        >>> c.get(1, "key")
        'v'
        >>> c.get(1, type=dict[str, int])
        {'key': 'v'}
        >>> c.get("key", default="missing")
        'missing'

        >>> c.get("key")
        Traceback (most recent call last):
        ...
        idanb.utils.config.ConfigTypeError: expected Mapping, found list (at .)

        >>> c.get(1, "key", type=int)
        Traceback (most recent call last):
        ...
        idanb.utils.config.ConfigTypeError: expected int, found str (at [1].key)

        >>> c.get(0, type=str, default="missing")
        Traceback (most recent call last):
        ...
        idanb.utils.config.ConfigTypeError: expected str, found int (at [0])

        """
        typ = type

        try:
            value = self._getvalue(*path, reload=True)
        except ConfigError:
            if default is NO_DEFAULT:
                raise
            return default

        if isinstance(typ, types.GenericAlias):
            typ = typ.__origin__
        typ = T.cast("type[Type]", typ)

        if isinstance(value, typ):
            return value

        if dataclasses.is_dataclass(typ):
            return self._makeinstance(typ, value, path)

        # Coerce `int` to `float`.
        if typ is float and isinstance(value, str):
            return T.cast("Type", float(value))

        raise ConfigTypeError(typ, builtins.type(value), path)

    def _getvalue(self, *path: str | int, reload: bool) -> object:
        if reload:
            _ = self.reload()

        value = self._data
        for i, key in enumerate(path):
            if isinstance(key, str):
                if not is_mapping(value):
                    raise ConfigTypeError(Mapping, type(value), path[:i])
            else:
                _ = T.assert_type(key, int)
                if isinstance(value, str | bytes) or not is_sequence(value):
                    raise ConfigTypeError(Sequence, type(value), path[:i])

            try:
                # Checks above made sure that `value` is indexable with `key`.
                value = T.cast("SupportsGetItem[str | int, object]", value)
                value = value[key]
            except LookupError as e:
                errmsg = "missing value"
                raise ConfigError(errmsg, path[: i + 1]) from e

        return value

    def _makeinstance[Cls](
        self,
        cls: type[Cls],
        data: object,
        path: tuple[str | int, ...],
    ) -> Cls:
        if not is_mapping(data, keys=str):
            raise ConfigTypeError(Mapping, type(data), path)

        try:
            instance = cls(**data)
        except (TypeError, ValueError, AssertionError) as e:
            errmsg = f"invalid config for {cls.__name__!r}"
            raise ConfigError(errmsg, path) from e

        self._cache[cls] = instance
        return instance

    def _getinstance[Cls](self, cls: type[Cls], *, reload: bool) -> Cls:
        if reload:
            _ = self.reload()

        cached: Cls | None = self._cache.get(cls)
        if cached is not None:
            return cached

        path = self._paths.get(cls)
        if path is None:
            errmsg = f"{cls.__qualname__!r} was not registered"
            raise TypeError(errmsg)

        data = self._getvalue(*path, reload=False)
        instance = self._makeinstance(cls, data, path)
        self._cache[cls] = instance
        return instance


class ConfigLoader[Data](abc.ABC):
    """Loads config from file and refreshes it whenever the file changes."""

    _path: Path
    _timestamp: int

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._timestamp = -1

    @abc.abstractmethod
    def load(self, path: Path) -> Data: ...

    def get(self) -> Config[Data]:
        return Config(self._load(), reload=self._refresh)

    def _load(self, mtime: int = -1) -> Data:
        if mtime < 0:
            mtime = self._path.stat().st_mtime_ns

        self._timestamp = mtime
        return self.load(self._path)

    def _refresh(self) -> Data | None:
        mtime = self._path.stat().st_mtime_ns
        return None if mtime == self._timestamp else self._load(mtime)


class TOMLConfigLoader(ConfigLoader[dict[str, object]]):
    @T.override
    def load(self, path: Path) -> dict[str, object]:
        import tomllib  # noqa: PLC0415

        with path.open("rb") as f:
            return tomllib.load(f)


class YAMLConfigLoader(ConfigLoader[dict[str, object]]):
    @T.override
    def load(self, path: Path) -> dict[str, object]:
        import yaml  # noqa: PLC0415

        with path.open("rb") as f:
            return yaml.safe_load(f)

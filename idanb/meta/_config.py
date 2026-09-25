from __future__ import annotations

import shutil

import typing_extensions as T

from idanb.utils.config import YAMLConfigLoader

from ._paths import rootdir

if T.TYPE_CHECKING:
    pass


CONFIG_PATH = rootdir() / "config.yaml"
CONFIG_EXAMPLE_PATH = rootdir() / "config.example.yaml"

if not CONFIG_PATH.exists():
    shutil.copy(CONFIG_EXAMPLE_PATH, CONFIG_PATH)

CONFIG = YAMLConfigLoader(CONFIG_PATH).get()

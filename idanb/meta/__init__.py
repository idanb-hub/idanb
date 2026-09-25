"""Information about the project and the executing environment."""

from . import (
    git as git,
)
from ._config import (
    CONFIG as CONFIG,
    CONFIG_EXAMPLE_PATH as CONFIG_EXAMPLE_PATH,
    CONFIG_PATH as CONFIG_PATH,
)
from ._env import (
    environment as environment,
    is_jupyterhub as is_jupyterhub,
    is_notebook as is_notebook,
    is_voila as is_voila,
    is_vscode as is_vscode,
)
from ._paths import (
    cachedir as cachedir,
    datadir as datadir,
    nbpath as nbpath,
    pkgdir as pkgdir,
    rootdir as rootdir,
    serverdir as serverdir,
)
from ._urls import (
    baseurl as baseurl,
    nburl as nburl,
    urlof as urlof,
)

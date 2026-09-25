"""General utilities."""

from . import (
    config as config,
    dicts as dicts,
    enums as enums,
    fs as fs,
    parse as parse,
)
from ._async import (
    ContextProxy as ContextProxy,
    forget_task as forget_task,
)
from ._cache import (
    cache as cache,
    fs_cache as fs_cache,
    lru_cache as lru_cache,
)
from ._decorator import (
    UniversalDecorator as UniversalDecorator,
    UniversalDecoratorBase as UniversalDecoratorBase,
    decorator as decorator,
    universaldecorator as universaldecorator,
)
from ._dicts import (
    CaselessDict as CaselessDict,
    TransformDict as TransformDict,
)
from ._exceptions import (
    log_exceptions as log_exceptions,
)
from ._functional import (
    then as then,
    void as void,
)
from ._immutable import (
    Record as Record,
)
from ._iotools import (
    TextIOAdapter as TextIOAdapter,
)
from ._typetools import (
    copy_annotations_from as copy_annotations_from,
    is_mapping as is_mapping,
    is_sequence as is_sequence,
    is_set as is_set,
)

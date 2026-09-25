from __future__ import annotations

from pathlib import Path

import typing_extensions as T
import anywidget
import traitlets

if T.TYPE_CHECKING:
    pass


class TextStream(anywidget.AnyWidget):
    _esm: str | Path = Path(__file__).with_suffix(".js")

    html: traitlets.Bool = traitlets.Bool(default_value=False).tag(sync=True)

    _snapshot: traitlets.Unicode = traitlets.Unicode().tag(sync=True)
    _buffer: list[str]

    def __init__(
        self,
        value: str = "",
        **kwargs: object,
    ) -> None:
        self._snapshot = value
        self._buffer = []
        super().__init__(**kwargs)

        self.on_msg(type(self).on_custom_msg)
        # Re-render contents when `html` is toggled.
        self.observe(lambda _: self.sync(), names=["html"])

    # Storing text in a trait would send the whole thing to frontend after every
    # write. Instead, we send custom messages with newly written text, which the
    # frontend appends to its state. Only when the frontend requests it (because
    # it lost its state), or when text is cleared, we send a snapshot with the
    # whole text.

    def write(self, text: str) -> None:
        """Append `text` to `self.value`."""
        self._buffer.append(text)
        self.send(text)

    def flush(self) -> None:
        """NOOP for compatibility with `TextIO`."""

    def clear(self) -> None:
        """Clear `self.value`."""
        self.value = ""

    def sync(self) -> None:
        """Force sync with frontend."""
        self._snapshot += "".join(self._buffer)
        self._buffer.clear()

    @property
    def value(self) -> str:
        return "".join((self._snapshot, *self._buffer))

    @value.setter
    def value(self, value: str) -> None:
        self._buffer.clear()
        self._snapshot = value

    def on_custom_msg(self, content: object, buffers: list[memoryview]) -> None:
        del buffers

        match content:
            case "sync":
                self.sync()
            case "clear":
                self.clear()
            case _:
                pass

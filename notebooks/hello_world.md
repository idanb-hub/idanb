# Example Notebook

## Environment Setup

This should be the first cell of every notebook.
Don't modify it unless you have to.
When imported, the `nbinit` module sets up the notebook's environment.
It also defines a logger, because everyone needs one.

```python
from __future__ import annotations

from idanb.nbinit import logger
```

## Imports

Unless you have a reason not to, put all imports at the start of the notebook.
One such reason would be when an import is used only by a single cell.
Consider moving such import the cell where it is used.

```python
import datetime

# UI framework.
import reacton

# Material UI components.
from ipymui.components import mui

# Custom UI components.
from idanb import ui
```

## Configuration

Configuration is loaded from `config.yaml` in the project's root directory.
Modules can define dataclasses and register them to be populated from this
global configuration.

```python
import pydantic.dataclasses
import yaml

# Global singleton that holds loaded configuration.
from idanb.utils.config import CONFIG


# Register configuration dataclass.
@CONFIG.register("hello_world")
# Like stdlib dataclass, but also validates field types.
@pydantic.dataclasses.dataclass()
class HelloWorldConfig:
    hello: str
    # Fields with default values are optional.
    optional: int = 0


# Override configuration loaded from `config.yaml` (which doesn't contain the
# `hello_world` section). Obviously, a real notebook wouldn't do this.
CONFIG.configure(yaml.safe_load("hello_world: { hello: world }"))

# Get configured instance of `HelloWorldConfig`.
hwconf = CONFIG[HelloWorldConfig]
display(hwconf)

# You can also query keys manually, but then you have to do validation yourself.
assert CONFIG["hello_world", "hello"] == "world"
assert CONFIG.get("hello_world", "optional") is None
```

## Reacton

React-like UI library. It handles state management and component composition.
but does not ship with any components.
For that, we use [`ipymui`](https://codeberg.org/steovd/ipymui#readme),
which exposes most of [Material UI components](https://mui.com/material-ui/all-components/)
as Jupyter widgets.

### Component Quickstart

```python
@reacton.component
def Range() -> None:  # noqa: N802
    # Think of the function as a render pass. When component state changes,
    # it is re-rendered by executing this function. Changes may come from
    # user's actions (e.g. button clicked) or from code (e.g. timeout expired).

    # State hooks allow to define state that persists between renders.
    lo, set_lo = reacton.use_state(0.0)
    hi, set_hi = reacton.use_state(100.0)

    # It's OK to use regular variables for inexpensive operations.
    mid = (lo + hi) / 2

    # UI layout is declared by calling component functions.
    # With statements are used to nest components (`with parent: children`).
    with mui.Stack(direction="column", margin=4):
        mui.Typography("Low")
        mui.Slider(value=lo, onChange=lambda _, value: set_lo(value))
        mui.Typography("High")
        mui.Slider(value=hi, onChange=lambda _, value: set_hi(value))
        mui.Typography("Middle")
        mui.Slider(value=mid, disabled=True)

    # Using the setter queues this component to be re-rendered (with modified
    # state), but only if the new value is not equal to the current one.
    set_hi(max(lo, hi))

    # NOTE: This would create an infinite loop.
    # set_hi(hi + 1)  # noqa: ERA001

    with mui.Stack(direction="row", gap=1):
        mui.Button(
            "Reset Low",
            # When clicked, the state will change, triggering re-render.
            onClick=lambda: set_lo(0.0),
            disabled=lo == 0.0,
        )
        mui.Button(
            "Reset High",
            onClick=lambda: set_hi(100.0),
            disabled=hi == 100.0,  # noqa: PLR2004
        )

    # Memos' values are memoized on first-render and recalulated only when their
    # dependencies (if any) change. Notably, they are useful for initializing
    # random values or dates/times.
    first = reacton.use_memo(
        lambda: datetime.datetime.now(datetime.UTC),
        dependencies=[],
    )
    current = datetime.datetime.now(datetime.UTC)
    mui.Alert(f"Component first rendered at {first}, last at {current}.")


Range()
```

The `Range` component doesn't use any global state, making it perfectly reusable.

```python
@reacton.component
def Ranges(count: int) -> None:  # noqa: N802
    with mui.Stack(direction="row", spacing=1):
        for _ in range(count):
            with mui.Stack(direction="column"):
                Range()


Ranges(2)
```

### Fundamentals

#### Components

The `@reacton.component` decorator is used for creating function components.
Function components combine other components, along with state and logic.

There are also widget components, which are the "foundational" components,
such as text, buttons, or layout containers. Every `ipywidgets` widget class
gains the `.element(**kwargs)` classmethod, using which a component can be
created from it.

To learn more about components, visit [Solara documentation](https://solara.dev/documentation).
I recommend at least reading about the fundamentals here:

- [Components](https://solara.dev/documentation/getting_started/fundamentals/components)
- [State Management](https://solara.dev/documentation/getting_started/fundamentals/state-management)

#### Hooks

In Reacton (and React), hooks are functions through which components interact
with the renderer. You've already seen two: `use_state` and `use_memo`.
By convention, hooks' names start with `use_`.

Hooks can only be used in function components, and must run in the same order
on every render.
See [Rules of Hooks](https://solara.dev/documentation/advanced/understanding/rules-of-hooks)
for more information and common pitfalls.

#### Further Reading

Aside from [Reacton's API docs](https://reacton.solara.dev/en/latest/api/),
the [Solara's Understanding chapter](https://solara.dev/documentation/advanced/understanding)
is a great resource for learning how things work.

### Tasks

Avoid expensive computations inside components - they block user interactions.
Instead, move them into tasks, which run in the background, and present the
results once they're ready.
For better UX, can show a progress bar or allow the task to be cancelled.

```python
import asyncio


@reacton.component
def Inverse() -> None:  # noqa: N802
    mui.Typography(
        "Calculate multiplicative inverse of number (very slowly)",
        variant="h4",
    )

    with mui.Stack(direction="column"):
        mui.Typography("Number")
        number, set_number = reacton.use_state(5)
        mui.Slider(
            value=number,
            onChange=lambda _, value: set_number(value),
            marks=True,
            step=1,
        )

        mui.Typography("Delay")
        delay, set_delay = reacton.use_state(2)
        mui.Slider(
            value=delay,
            onChange=lambda _, value: set_delay(value),
            marks=True,
            step=1,
        )

    progress, set_progress = reacton.use_state(0.0)

    # This decorator turns an async function into a `Task` state variable.
    # Tasks are executed in the background to avoid blocking UI. Attributes
    # `.pending`, `.exception` and `.result` describe the computation state
    # and result.
    @ui.use_task()
    async def inverse() -> float:
        for i in range(delay * 10):
            # Can be any float, but progress bar expects numbers from 0 to 100.
            set_progress((i + 1) / delay * 10)
            await asyncio.sleep(0.1)
        # This raises when number is zero.
        return 1 / number

    if inverse.pending:
        mui.LinearProgress(variant="determinate", value=progress)
    elif inverse.exception is not None:
        mui.Alert(str(inverse.exception), severity="error")
    elif inverse.result is not inverse.NO_RESULT:
        mui.Alert(f"Multiplicative inverse: {inverse.result}", icon=False)

    mui.Button(
        "Recalculate" if not inverse.pending else "Cancel",
        onClick=lambda: inverse() if not inverse.pending else inverse.cancel(),
        color="primary" if not inverse.pending else "error",
    )


Inverse()
```

## AnyWidget

Low level library for writing custom widgets.

```python
# https://anywidget.dev/en/getting-started/#example

import anywidget
import traitlets


class CounterWidget(anywidget.AnyWidget):
    _esm = """
    function render({ model, el }) {
      let button = document.createElement("button");
      button.innerHTML = `count is ${model.get("value")}`;
      button.addEventListener("click", () => {
        model.set("value", model.get("value") + 1);
        model.save_changes();
      });
      model.on("change:value", () => {
        button.innerHTML = `count is ${model.get("value")}`;
      });
      el.classList.add("counter-widget");
      el.appendChild(button);
    }
    export default { render };
    """

    _css = """
    .counter-widget button {
      color: white;
      font-size: 1.75rem;
      background-color: #ea580c;
      padding: 0.5rem 1rem;
      border: none;
      border-radius: 0.25rem;
    }
    .counter-widget button:hover {
      background-color: #9a3412;
    }
    """

    value = traitlets.Int(0).tag(sync=True)


CounterWidget(value=42)
```

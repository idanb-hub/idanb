# Example Notebook

## Environment Setup

This should be the first cell of every notebook.
Don't modify it unless you have to.
It finds and runs the `nbinit` script, which sets up the notebook's environment.
It also defines a logger, because everyone needs one.

```python
from __future__ import annotations

from idanb.nbinit import logger, nbinit  # noqa: F401

nbinit()
```

## Imports

After `nbinit` has run, you can also import contents of `src/` directory.

```python
import datetime

# UI components.
import solara
import solara.lab

# Custom UI components.
from idanb import components
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

## Solara

React-like UI library.

### Component Quickstart

```python
@solara.component
def Range() -> None:  # noqa: N802
    # Think of the function as a render pass. When component state changes,
    # it is re-rendered by executing this function. Changes may come from
    # user's actions or from code in this function.

    # Reactive variables persist between renders. They hold the component state.
    lo = solara.use_reactive(0.0)
    hi = solara.use_reactive(10.0)

    # Use `.get()` to read reactive's current value.
    mid = (lo.get() + hi.get()) / 2

    # UI layout is declared by calling component functions.
    # With statements are used to nest components (`with parent: children`).
    # Here, the `LocalCSS` component applies CSS rules to its children.
    with components.LocalCSS({".v-label": "width: 6ex;"}):
        # Reactive variables can receive values from input components.
        solara.SliderFloat(label="Low", value=lo)
        solara.SliderFloat(label="High", value=hi)
        # You can also use "normal" values, but those are output-only.
        solara.SliderFloat(label="Middle", value=mid, disabled=True)

    # Use `.set()` to set reactive's value. If the new value is different
    # from the previous one, the component will be re-rendered.
    hi.set(max(lo.get(), hi.get()))

    # NOTE: This would create an infinite loop.
    # hi.set(hi.get() + 1)  # noqa: ERA001

    # Implicitly, components are laid out in `solara.Column()`.
    with solara.Row():
        solara.Button(
            label="Reset Low",
            # When clicked, reactive's value will change, triggering re-render.
            on_click=lambda: lo.set(0.0),
            color="primary",
            disabled=lo.get() == 0.0,
        )
        solara.Button(
            label="Reset High",
            on_click=lambda: hi.set(10.0),
            color="primary",
            disabled=hi.get() == 10.0,  # noqa: PLR2004
        )

    # Memos' values are memoized on first-render. Notably, they are useful for
    # initializing random values or dates/times.
    first = solara.use_memo(lambda: datetime.datetime.now())  # noqa: DTZ005
    current = datetime.datetime.now()  # noqa: DTZ005
    solara.Info(f"Component first rendered at {first}, last at {current}.")


Range()
```

The `Range` component doesn't use any global state, making it perfectly reusable.

```python
@solara.component
def Ranges(count: int) -> None:  # noqa: N802
    with solara.Row():
        for _ in range(count):
            with solara.Column(style="flex: 1;"):
                Range()


Ranges(3)
```

### Fundamentals

#### Components

The `component` decorator is used for creating function components.
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

In solara (and React), hooks are functions through which components interact
with the renderer. You've already seen two: `use_reactive` and `use_memo`.
By convention, hooks' names start with `use_`.

Hooks can only be used in function components, and must run in the same order
on every render.
See [Rules of Hooks](https://solara.dev/documentation/advanced/understanding/rules-of-hooks)
for more information and common pitfalls.

#### Further Reading

Aside from the [API docs](https://solara.dev/documentation/api),
the [Understanding](https://solara.dev/documentation/advanced/understanding)
chapter is a great resource for learning how things work.

Note that in some places, those docs haven't been updated to use the new,
now preferred features, and show the outdated ways of doing things instead,
such as:

- `use_state` (old, bad) instead of `use_reactive` (new, good)
- unnecessary global state (`reactive`) instead of component-local state (`use_reactive`)

### Tasks

Avoid expensive computations inside components - they block user interactions.
Instead, move them into tasks, which run in the background, and present the
results once they're ready.
For better UX, can show a progress bar or allow the task to be cancelled.

```python
import asyncio


@solara.component
def Inverse() -> None:  # noqa: N802
    solara.HTML(
        "h2",
        "Calculate multiplicative inverse of number (very slowly)",
    )

    with components.LocalCSS({".v-label": "width: 6ex;"}):
        number = solara.use_reactive(5)
        solara.SliderInt(label="Number", value=number, tick_labels=True)

        delay = solara.use_reactive(2)
        solara.SliderInt(label="Delay", value=delay, tick_labels=True)

    # This decorator turns a function into a `Task` variable, that has a number
    # of read-only reactive attributes. Tasks are executed in the background to
    # avoid blocking UI. Attributes `.pending`, `.progress` and `.value`
    # describe the computation state and result.
    @solara.lab.use_task(
        # Task is automatically re-executed when its dependencies change.
        dependencies=[number.get()],
        # Catch raised exceptions into the `.exception` reactive attribute.
        raise_error=False,
    )
    async def inverse() -> float:
        d = delay.get()
        for i in range(d * 10):
            # Can be any float, but progress bar expects numbers from 0 to 100.
            inverse.progress = (i + 1) / d * 10
            await asyncio.sleep(0.1)
        # This raises when number is zero.
        return 1 / number.get()

    solara.ProgressLinear(inverse.progress or 0 if inverse.pending else False)

    if inverse.finished:
        assert inverse.value is not None
        solara.Info(f"Multiplicative inverse: {inverse.value}", icon=False)
    elif inverse.error:
        assert inverse.exception is not None
        solara.Error(str(inverse.exception))

    # Custom button component for controlling tasks.
    # If the task is already pending, clicking this cancels it.
    components.TaskButton(
        task=inverse,
        label="Recalculate",
        # These are applied only if the task is pending.
        if_pending={
            "label": "Cancel",
            "color": "error",
        },
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

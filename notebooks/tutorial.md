# Example Notebook

This notebook explains how to write notebooks using the IdaNB framework.

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
One such reason would be when an import is used only by a single cell,
then it may kept in that one cell.

```python
import asyncio
from datetime import UTC, date, datetime

import typing_extensions as T
import ipymui
from ipymui.components import html, mui

from idanb import react, utils
```

## Configuration

Configuration is loaded from [`config.yaml`](../config.yaml)
(found in the root directory of the project).
The `meta.CONFIG` singleton provides access to this configuration.

```python
from idanb.meta import CONFIG

# For demonstration purposes only: override the configuration.
CONFIG.data = {"example": {"name": "joe", "age": 12}}
```

```python
# Get value by path.
name = CONFIG.get("example", "name")
# Get value by path and check its type.
age = CONFIG.get("example", "age", type=int)
# Get value by path or default if missing.
job = CONFIG.get("example", "job", default="unemployed")

name, age, job
```

Instead of reading config values one by one, you can define a dataclass
and register it to be later instantiated from the configuration.

```python
import pydantic.dataclasses


# Register configuration dataclass.
@CONFIG.register("example")
# Like stdlib dataclass, but also validates field types.
@pydantic.dataclasses.dataclass()
class ExampleConfig:
    name: str
    age: int
    # Fields with default values are optional.
    job: str = "unemployed"


# Create an instance from the configuration.
conf = CONFIG[ExampleConfig]
conf
```

## User Interface

Notebook UI is composed from `ipymui` components using functions from
`idanb.react`.

Think of the `ipymui` components as building blocks and the `react` functions
as glue that is used to stitch them together.

### `ipymui` HTML components

All `ipymui` components use the same argument convention:

- positional arguments are children:
  strings, elements (instances of components), and other
- keyword arguments are attributes (also known as _props_)

```python
html.select(
    html.option("one", value=1),
    html.option("two", value=2),
    defaultValue=1,
    style=dict(fontSize="2em"),
)
```

<!-- #region -->

The above code renders as the following HTML:

```html
<select value=1 style="font-size: 2em">
    <option value=1>one</option>
    <option value=2>two</option>
</select>
```

Notice how `style` properties get converted from camelCase to snake-case.

<div class="alert alert-block alert-info">

When specifying props, prefer the `dict` constructor over dictionary literals
(`{}`), which are less readable when there are many keys.

</div>

<!-- #endregion -->

### Custom Components

Custom UI components are written as functions with the `react.component`
decorator.
The body of such a function represents a single render pass of its component.
Whenever component state changes, its function is called to re-render it.

The `react.use_state` function preserves component state between renders.
Given an initial state, it returns the current state and a setter function.
When the setter is called, it changes the state for subsequent renders
and schedules the component to be re-rendered (to show its new state).

```python
@react.component
def Counter() -> None:  # noqa: N802
    count, set_count = react.use_state(0)

    html.button(
        f"counter={count}",
        onClick=lambda: set_count(lambda count: count + 1),
    )


Counter()
```

The convention is to use PascalCase when naming components,
as if they were classes.
Unfortunately, Ruff complains about it.
A `noqa` comment is needed to silence the error.

<div class="alert alert-block alert-info">

If the new state is derived from the current state,
instead of setting it directly, you should give the setter an _updater_ function
to avoid possible concurrency issues (read more about it
[here][https://react.dev/reference/react/useState#updating-state-based-on-the-previous-state]).

</div>

### Component State Hooks

React hooks are functions give components access to their state and context.
The `use_state` function from above is one example, but there are others:

- `use_memo`: Memoize function calls between renders.
- `use_effect`: Call functions when state changes or component is created/destroyed.
- `use_context`: Get and set context state variables.
- `use_global`: Get and set global state variables.
- `use_task`: Call async functions across renders.

### Complex Component State

If the state of your component consists of many variables,
consider combining them into a _store_.

Essentially, store is a dataclass (derived from `utils.immutable.Record`).
The `react.use_store` function works the same as `react.use_state`,
except its setter has an overload for setting individual store fields.

```python
class ToDoStore(utils.immutable.Record):
    eat: bool = False
    sleep: bool = False
    repeat: bool = False


@react.component
def ToDoList() -> None:  # noqa: N802
    todos, set_todos = react.use_store(ToDoStore())

    html.button(
        "Eat",
        onClick=lambda: set_todos(eat=True),
        disabled=todos.eat,
    )
    html.button(
        "Sleep",
        onClick=lambda: set_todos(sleep=True),
        disabled=todos.sleep,
    )
    html.button(
        "Repeat",
        onClick=lambda: set_todos(repeat=True),
        disabled=todos.repeat,
    )

    html.br()
    html.button("RESET", onClick=lambda: set_todos(ToDoStore()))


ToDoList()
```

### Component Composition

Inside component functions, you can nest elements by using them as context
managers.
This syntax enables you to combine component calls with other statements,
namely branching and loops.

For example:
`with Parent(): Child(), Child()` is equivalent to `Parent(Child(), Child())`.

```python
@react.component
def Chooser(*options: str, title: str) -> None:  # noqa: N802
    with html.fieldset():
        html.legend(title)
        for option in options:
            with html.label():
                html.input(type="radio", name="choice", value=option)
                html.Fragment(option)
            html.br()


Chooser("Kraken", "Sasquatch", "Mothman", title="Choose your favorite monster")
```

Children of `html.Fragment` are inlined into its parent during rendering.
Use fragments to add strings or already-created elements as children of
the current parent element context.

<div class="alert alert-block alert-info">

Avoid expensive logic inside components - it blocks user interaction.
Instead, use the `react.use_task` hook to run tasks in the background
and present their results once they finish.

</div>

### Component Callbacks

If your custom component needs to communicate with its parent,
as most input components do, it should take a callback among its arguments.
By convention, these callbacks are often named `on_*`:
`on_change`, `on_submit`, `on_cancel`.
If your component contains multiple inputs and accepts multiple `<value>`
arguments, their respective change callbacks should be named `on_<value>`.

```python
@react.component
def Search(  # noqa: N802
    value: str = "",
    on_submit: T.Callable[[str], None] | None = None,
) -> None:
    if on_submit is None:
        on_submit = lambda _: None  # noqa: E731

    # https://react.dev/reference/react-dom/components/form#handle-form-submission-with-an-action-prop
    def submit(formdata: dict[str, str]) -> None:
        query = formdata["query"]
        on_submit(query)

    with html.form(action=submit):
        html.input(
            type="search",
            name="query",  # key in formdata
            defaultValue=value,
        )
        html.button("Search", type="submit")


Search()
```

<div class="alert alert-block alert-info">

Define default values for component arguments where possible.
It makes components much easier to test.

</div>

```python
@react.component
def SearchExample() -> None:  # noqa: N802
    query, set_query = react.use_state("")

    Search(value=query, on_submit=set_query)

    if query:
        html.div(f"No results for: {query}")


SearchExample()
```

### Listening for Frontend Callbacks

```python
@react.component
def Password() -> None:  # noqa: N802
    value, set_value = react.use_state(0)

    with html.div():
        html.input(
            type="range",
            value=value,
            onChange=ipymui.callback("$[0].target.value")(set_value),
            style=dict(verticalAlign="middle"),
        )

        html.span(str(value))


Password()
```

The `ipymui.callback` decorator annotates a callback function with JavaScript
expressions that specify what arguments it receives from the frontend.
In these expressions, `$` refers to the original arguments
(`$[0]` being the first argument).
A JavaScript equivalent to the above callback is
`(e) => setValue(e.target.value)`.

Consider using callbacks other than `onChange` to minimize re-renders.
For example, with a text input, `onChange` triggers after every keystroke.
Often, `onBlur` (runs when input loses focus) may be a better choice.
If you only need the inputs once the user clicks a button,
consider wrapping them in a form and use its `action` instead.

```python
@react.component
def Password() -> None:  # noqa: N802
    password, set_password = react.use_state("")

    with html.div():
        html.input(
            type="password",
            defaultValue=password,
            # Causes `defaultValue` to be re-applied when `key` changes.
            key=password,
            onBlur=ipymui.callback("$[0].target.value")(set_password),
            style=dict(verticalAlign="middle"),
        )

        if not password:
            html.span()
        elif password == password.lower() or password == password.upper():
            html.span(
                "password must contain both lower- and upper-case characters"
            )
        else:
            html.span("good enough")

    html.button("randomize", onClick=lambda: set_password("Random123"))


Password()
```

### `ipymui` Material UI Components

Besides standard HTML, the `ipymui` package also includes Material UI components.
These components come with built-in functionality and styling,
which makes building custom UIs much easier.

- MUI component list: https://mui.com/material-ui/all-components/

Consult `ipymui`'s [README](https://codeberg.org/steovd/ipymui#readme) for more
details.
If you ever used React before, `ipymui` components should look familiar.
If not, you may take insiration from existing notebooks or from
[`ipymui` examples](https://codeberg.org/steovd/ipymui/src/branch/master/examples).

```python
class User(utils.immutable.Record):
    name: str = "John Doe"
    born: date = date(1995, 8, 17)
    bio: str = "I don't like garlic."


@react.component
def UserProfile() -> None:  # noqa: N802
    state, set_state = react.use_store(User())

    with mui.Grid(container=True, spacing=1, sx=dict(my=1)):
        with mui.Grid(size=6), mui.Stack(spacing=1):
            mui.TextField(
                label="Name",
                defaultValue=state.name,
                key=state.name,
                onBlur=ipymui.callback("$[0].target.value")(
                    lambda value: set_state(name=value),
                ),
            )

            mui.date_pickers.DatePicker(
                label="Date of Birth",
                value=state.born,
                onChange=lambda value: set_state(
                    born=datetime.fromisoformat(value).date()
                ),
            )

            mui.TextField(
                label="Bio",
                defaultValue=state.bio,
                key=state.bio,
                rows=3,
                multiline=True,
                onBlur=ipymui.callback("$[0].target.value")(
                    lambda value: set_state(bio=value),
                ),
            )

            mui.Button(
                "Reset",
                onClick=lambda: set_state(User()),
                # https://mui.com/material-ui/material-icons/
                startIcon=mui.icons.RestartAlt(),
            )

        with mui.Grid(size=6), mui.Card():
            mui.CardHeader(title=state.name, avatar=mui.Avatar(state.name[:1]))
            with mui.CardContent():
                with mui.Table(), mui.TableBody():
                    with mui.TableRow():
                        mui.TableCell("Born")
                        mui.TableCell(state.born.strftime("%b %d %Y"))
                    with mui.TableRow():
                        mui.TableCell("Age")
                        age = datetime.now(UTC).date() - state.born
                        mui.TableCell(age.days // 365)

                mui.Typography("Bio", variant="h6", sx=dict(mt=1))
                mui.Typography(state.bio, sx=dict(mt=1))


UserProfile()
```

Instead of `style`, MUI components use the `sx` prop.
Essentially, `sx` is a superset of `style`. Its extra features include:

- color variables: use colors from theme
- unit scaling: leave units out to use multiples of theme values
- shorthands for common properties
- and more: https://mui.com/system/getting-started/the-sx-prop/

### Tabs

Example adapted from [MUI docs](https://mui.com/material-ui/react-tabs/#introduction).

```python
@react.component
def TabsExample() -> None:  # noqa: N802
    tab, set_tab = react.use_state(1)

    with mui.Tabs(value=tab, onChange=lambda _, value: set_tab(value)):
        mui.Tab(label="one", value=1)
        mui.Tab(label="two", value=2)
        mui.Tab(label="three", value=3)

    with mui.Box(hidden=(tab != 1)):
        mui.Typography("Item one")

    with mui.Box(hidden=(tab != 2)):  # noqa: PLR2004
        mui.Typography("Item two")

    with mui.Box(hidden=(tab != 3)):  # noqa: PLR2004
        mui.Typography("Item three")


TabsExample()
```

### Tasks

The `react.use_task` hook is wraps an asynchronous function into a reactive
`asyncio.Task`-like variable.
Its `.start(...)` and `.cancel()` methods control is execution,
and its `.status` attribute exposes its status.

```python
@react.component
def Timer() -> None:  # noqa: N802
    @react.use_task()
    async def delay(seconds: int) -> int:
        await asyncio.sleep(seconds)
        return seconds

    button_props = ipymui.Props(variant="contained", fullWidth=True)
    if delay.pending:
        mui.Button("Stop", onClick=delay.cancel, color="error", **button_props)
    else:
        mui.Button("Start", onClick=lambda: delay.start(3), **button_props)

    match delay.status:
        case delay.Exception(e):
            mui.Alert(str(e), severity="error")
        case delay.Pending():
            mui.LinearProgress()
        case delay.Result(seconds):
            mui.Alert(f"{seconds} seconds elapsed.")
        case delay.Cancelled():
            mui.Alert("Task cancelled.", severity="warning")
        case delay.NotCalled():
            pass


Timer()
```

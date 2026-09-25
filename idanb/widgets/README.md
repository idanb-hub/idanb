# Custom Jupyter widgets

Custom widgets provide features that can only be implemented at the front-end.
They are written using [`anywidget`](anywidget).

Front-end JavaScript code uses [JSDoc] type annotations.
They are more verbose than TypeScript, but don't require a transpiler.

## Structure

Each widget consists of two files: Python back-end and JavaScript front-end.
Private files (`_*`) hold shared code that is used across multiple widgets.

When rendered in Voila, each widget back-end module runs its corresponding
IPython script (`*.ipy`) that acts as live preview of the widget.

[jsdoc]: https://www.typescriptlang.org/docs/handbook/jsdoc-supported-types.html

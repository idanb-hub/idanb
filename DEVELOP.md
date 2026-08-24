# Analytical notebooks - Development

## Project structure

```
.
├─ config/                     static configuration
├─ notebooks/                  Jupyter notebooks
├─ packages/                   Python packages
│  ├─ labconfig/               JupyterLab configuration
│  └─ idanb-lib/               Python modules (git submodule)
│     └─ src/
│        └─ idanb/
│           ├─ core/           features shared between notebooks
│           ├─ infra/          connectors to infrastructure
│           ├─ meta/           information about project and environment
│           ├─ nbinit/         notebook initialization
│           ├─ ui/             custom UI components and widgets
│           └─ utils/          standalone utilities
├─ typings/                    type stubs (.pyi)
└─ config.yaml                 user-specific configuration
```

## Writing notebooks

Notebooks checked into version control are written in Markdown.
From these, `.ipynb` notebooks are generated using
[Jupytext](https://jupytext.readthedocs.io).

In JupyterLab, the Jupytext extension automatically synchronizes between the
two formats. In VS Code, there is an extension to do the same, but you have to
[install it yourself](https://jupytext.readthedocs.io/en/latest/vs-code.html).

You can synchronize manually with `uv run jupytext --sync notebooks/**/*.md`.
On Windows, you might have to list the notebook paths explicitly instead of
using globs.

## Pre-commit

[Prek](https://prek.j178.dev/) is configured to check staged code before
each commit.
However, you first need to enable it:

```python
! uv run prek install
```

## Developer mode

In production mode, most notebooks only work in Voila. During local development,
set `developer: true` in [config.yaml](./config.yaml) to enable developer mode.

In developer mode, notebooks also work in JupyterLab (localhost only) and
VS Code (with some visual glitches).
Furthermore, autoreload of modules is enabled and Voila preview reloads whenever
the notebook is saved (you can use it even when editing in VS Code).

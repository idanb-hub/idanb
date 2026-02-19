# IdaNB

<!--
This README is also a functioning Jupytext notebook.
In JupyerLab (with the Jupytext extension), code blocks can be executed.
The `!` in each code block is IPython magic for running shell commands.
-->

## Requirements

<!-- https://docs.gitlab.com/user/markdown/#alerts don't work in JupyterLab -->

**NOTE**: In JupyterHub, all requirements are handled automatically.

The only requirement you need upfront is [uv](https://docs.astral.sh/uv/).
If haven't already, you can install it using your system's package manager.
Alternatively, or if you're on Windows, you can also use `pip`.

```python
! pip install uv
```

## Set up

After cloning the repository (or pulling new changes),
run the bootstrap script to install dependencies and generate notebooks.
Dependencies are installed into an isolated virtual environment.

In JupyterHub, if `uv` is not already installed, the bootstrap script installs
it too.

```python
! ./bootstrap.py
```

## Launch

Use `uv run jupyter-lab` to launch JupyterLab from the virtual environment.
Configuration and extensions installed outside of the virtual environment should
be available (you can check with `uv run jupyter --paths --debug`).

JupyerHub deployments require additional configuration, which is not yet
documented.

## Configuration

User-specific configuration goes in `config.yaml`.
This includes credentials to services without which notebooks won't work.
You can use [`config.example.yaml`](./config.example.yaml) as a starting point.

## Development

See [DEVELOP.md](./DEVELOP.md).

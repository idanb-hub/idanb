from __future__ import annotations

import os
import sys

import typing_extensions as T


def is_notebook() -> bool:
    return "JPY_SESSION_NAME" in os.environ


def is_voila() -> bool:
    return "VOILA_REQUEST_URL" in os.environ


def is_vscode() -> bool:
    return "__vsc_ipynb_file__" in vars(sys.modules["__main__"])


def environment() -> T.Literal[
    "",
    "notebook",
    "voila",
    "vscode",
]:
    if is_vscode():
        return "vscode"
    if is_voila():
        return "voila"
    if is_notebook():
        return "notebook"

    return ""


def is_jupyterhub() -> bool:
    return "JUPYTERHUB_HOST" in os.environ

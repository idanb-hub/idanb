from __future__ import annotations

from pathlib import Path

import typing_extensions as T
import pygit2

from idanb import utils

from ._paths import rootdir


@utils.cache
def repo() -> pygit2.Repository:
    """Get the git repository of this project."""
    return pygit2.Repository(rootdir())


_repo = repo


def follow(
    path: str | Path,
    *,
    repo: pygit2.Repository | None = None,
    start: str | pygit2.Oid | None = None,
    order: pygit2.enums.SortMode = pygit2.enums.SortMode.NONE,
    merges: bool = True,
) -> T.Iterator[pygit2.Commit]:
    """Follow git history of a specific file.

    Args:
        path: Path to follow, relative to repository root.
        repo: Repository to search. Defaults to `repo()`.
        start: Commit from which to start searching. Defaults to HEAD.
        order: Order in which to walk commits (see `pygit2.walk`).
        merges: Whether to include merge commits.

    Yields:
        Commit that changed `file`.
    """
    path = Path(path)

    if repo is None:
        repo = _repo()

    if start is None:
        start = repo.head.target

    # Based on:
    #   https://github.com/rust-lang/git2-rs/issues/588#issuecomment-658510497
    #   https://github.com/TortoiseGit/TortoiseGit/blob/REL_2.17.0.2_EXTERNAL/src/TortoiseShell/GITPropertyPage.cpp#L367
    for commit in repo.walk(start, order):
        if not merges and len(commit.parents) > 1:
            continue
        if _is_path_in_commit(repo, commit, path):
            yield commit


def _is_path_in_commit(
    repo: pygit2.Repository,
    commit: pygit2.Commit,
    path: Path,
) -> bool:
    # If a commit has no parents, diff against an empty tree.
    parents = commit.parents or [None]

    # Deltas against every parent must include a change to `path`.
    for parent in parents:
        deltas = repo.diff(commit, parent).deltas
        if path not in (Path(delta.new_file.path) for delta in deltas):
            return False

    return True

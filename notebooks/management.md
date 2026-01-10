# Project Management

Easy-to-use functions for managing this repository.

<details>
<summary>Maintainers</summary>

- **Milan Cermak** ([cermak@ics.muni.cz](mailto:cermak@ics.muni.cz))
- Stepan Dvorsky ([dvorsky@ics.muni.cz](mailto:dvorsky@ics.muni.cz))

</details>

```python
from __future__ import annotations

from idanb.nbinit import logger, nbinit, rootdir

nbinit()
```

```python
import asyncio
import functools
import itertools
import shlex
import subprocess
import typing
from datetime import UTC, datetime, timedelta, timezone

import pygit2
import solara
import solara.lab

if typing.TYPE_CHECKING:
    from pathlib import Path

    import typing_extensions as T
```

```python
async def run(
    cmd: str | T.Iterable[str],
    *,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    args = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)

    # Asyncio subprocess API doesn't work in IPython on Windows, because IPython
    # uses older EventLoop implementation which doesn't support subprocesses.
    # Once they migrate to `ProactorEventLoop`, this commit can be reverted.
    # See:
    #   https://github.com/ipython/ipykernel/issues?q=ProactorEventLoop
    result = await asyncio.to_thread(
        subprocess.run,
        args=args,
        stdin=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    logger.info("Subprocess '%s' finished.", args[0], **vars(result))

    if check:
        result.check_returncode()

    return result
```

```python
# Idea is to use pygit2 API to read repository state and git CLI to modify it.
# This way we don't have to parse CLI output nor do we have to bother with
# low-level API functions to mimic what can be done with a simple CLI command.

repo = pygit2.Repository(rootdir)
```

## Update Project

Update all files in this project to their latest version.
**Local changes will be reverted!** Don't forget so save your work before updating.

Open notebooks must be reloaded for the updates to take effect.
If JupyterLab asks you which file version to use, choosing **Revert** will get
you the updated version.

```python
def is_rebase_safe() -> bool:
    head = repo.head.shorthand
    if head == "HEAD":
        errmsg = "HEAD is detached"
        raise RuntimeError(errmsg)

    branch = repo.branches[head]

    if branch.upstream is None:
        errmsg = "upstream is gone"
        raise RuntimeError(errmsg)

    merge_result, _ = repo.merge_analysis(branch.upstream.target)

    if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
        if branch.target != branch.upstream.target:  # noqa: SIM103
            # Happens when local is ahead of upstream.
            return False
        # Up to date.
        return True
    if merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:  # noqa: SIM103
        # Behind, can fast forward.
        return True

    # Don't know, assume it's unsafe.
    return False
```

```python
def get_upstream_commits() -> list[pygit2.Commit]:
    branch = repo.branches[repo.head.shorthand]
    head = repo.head.target
    # This assumes upstream is ahead of local HEAD.
    return list(
        itertools.takewhile(
            lambda commit: commit.id != head,
            repo.walk(branch.upstream.target),
        )
    )
```

```python
@solara.component
def CommitLog(commits: list[pygit2.Commit]) -> None:  # noqa: N802
    for commit in commits:
        solara.Text(commit.message)
```

```python
@solara.lab.task()
async def fetch() -> datetime:
    await run("git fetch --verbose --prune", check=True)
    # Can be observed to know when fetch finished.
    new_commits()
    return datetime.now(tz=UTC)


@solara.lab.task()
def new_commits() -> list[pygit2.Commit]:
    if not is_rebase_safe():
        errmsg = "cannot update, git reset needed"
        raise RuntimeError(errmsg)
    return get_upstream_commits()
```

```python
@solara.component
def FetchPage() -> None:  # noqa: N802
    # Automatically fetch on first render.
    solara.use_memo(lambda: fetch())

    solara.Button(
        label="Check Updates",
        on_click=fetch,
        color="primary" if not new_commits.value else "secondary",
        disabled=fetch.pending,
    )

    solara.ProgressLinear(fetch.pending)
    if fetch.error:
        solara.Error(str(fetch.exception or "Error"))

    if not fetch.finished:
        return

    if new_commits.error:
        solara.Error(str(new_commits.exception or "Error"))
    elif new_commits.finished:
        if not new_commits.value:
            solara.Info("You're up to date!")
        else:
            with solara.Details(f"{len(new_commits.value)} new commits"):
                CommitLog(new_commits.value)
```

```python
from pygit2.enums import FileStatus

STATUS_MESSAGE = {
    # Worktree first (higher priority).
    FileStatus.WT_DELETED: "deleted",
    FileStatus.WT_MODIFIED: "modified",
    FileStatus.WT_NEW: "new file",
    FileStatus.WT_RENAMED: "renamed",
    FileStatus.WT_TYPECHANGE: "typechange",
    FileStatus.WT_UNREADABLE: "unredable",
    # Index after worktree.
    FileStatus.INDEX_DELETED: "deleted",
    FileStatus.INDEX_MODIFIED: "modified",
    FileStatus.INDEX_NEW: "new file",
    FileStatus.INDEX_RENAMED: "renamed",
    FileStatus.INDEX_TYPECHANGE: "typechange",
}


@solara.component
def ChangedFilesList(files: dict[str, pygit2.enums.FileStatus]) -> None:  # noqa: N802
    with solara.Column(gap="0"):
        for file, status in files.items():
            how = next(
                (msg for mask, msg in STATUS_MESSAGE.items() if status & mask),
                "unknown",
            )
            how += ":"

            solara.Text(
                f"{how:12} {file}",
                style={
                    "font-family": "monospace",
                    "white-space": "pre",
                },
            )
```

```python
@solara.component
def RestoreDialog(  # noqa: N802
    *,
    show: solara.Reactive[bool] | bool,
    then: T.Callable[[], None] = lambda: None,
) -> None:
    """Show confirmation dialog and run `git restore`.

    The dialog lists changed files and asks the user for permission to revert
    the changes. If they click OK, changes are reverted and `then` is ran,
    otherwise nothing happens.

    Args:
        show: Whether to show the dialog or not.
        then: Function to run after changes are reverted.
    """
    show = solara.use_reactive(show)

    changes = solara.use_reactive({})

    if not solara.use_previous(show.get()) and show.get():
        # Runs once every time dialog is opened (`show` changes to `True`).
        changes.set(repo.status(untracked_files="no"))
        if not changes.get():
            # Skip dialog if there are no changes.
            show.set(False)
            then()

    @solara.lab.use_task(dependencies=None, raise_error=False)
    async def restore() -> None:
        # The ":/" is magic pathspec for repository root.
        await run("git restore --staged --worktree :/", check=True)
        then()

    with solara.lab.ConfirmationDialog(
        title="Revert local changes?",
        open=show,
        on_ok=restore,
    ):
        solara.Text("If you click OK, these changes will be reverted:")
        ChangedFilesList(changes.get())
```

```python
@solara.component
def RebasePage() -> None:  # noqa: N802
    @solara.lab.use_task(dependencies=None, raise_error=False)
    async def update() -> None:
        # Rebase targets upstream by default (what we want).
        await run("git rebase", check=True)
        new_commits()
        # Bootstrap script syncs dependencies and notebooks.
        await run(str(rootdir / "bootstrap.py"), check=True)

    show_restore_dialog = solara.use_reactive(False)
    RestoreDialog(
        show=show_restore_dialog,
        then=update,
    )

    solara.Button(
        label="Update",
        on_click=lambda: show_restore_dialog.set(True),
        disabled=update.pending or not new_commits.value,
        color="primary",
    )

    solara.ProgressLinear(update.pending)
    if update.error:
        solara.Error(str(update.exception or "Error"))
```

```python
@solara.component
def UpdatePage() -> None:  # noqa: N802
    FetchPage()
    RebasePage()


UpdatePage()
```

## Manage Files

Here a some shortcuts for common file operations.

### Delete Duplicated Files

Notebook files have to be duplicated in order to run multiple instances of the
same notebook simultaneously. You can quickly delete leftover duplicates here.

```python
def find_files(glob: str, subdir: str | Path = ".") -> T.Iterable[str]:
    startdir = rootdir / subdir
    return (
        str(path.relative_to(rootdir))
        for path in startdir.rglob(glob)
        if path.is_file()
    )


def delete_files(files: T.Iterable[str]) -> T.Iterable[str]:
    for path in files:
        fullpath = rootdir / path
        try:
            fullpath.unlink(missing_ok=True)
        except OSError:
            logger.exception("Failed to delete file", path=path)
        else:
            logger.info("File deleted", path=path)
            yield path
```

```python
@solara.component
def FindAndDeleteFiles(  # noqa: N802, PLR0913
    *,
    glob: str,
    subdir: str = ".",
    files: solara.Reactive[dict[str, bool]] | dict[str, bool] | None = None,
    subject: str = "files",
    pending: solara.Reactive[bool] | None = None,
    disabled: bool = False,
) -> None:
    """Component for finding, selecting, and deleting files.

    Args:
        glob: Glob pattern of files to find.
        subdir: Path relative to repository root to search.
        files: Dictionary holding found files and whether they are selected.
        subject: Human-readable summary of `glob` (shown in UI).
        pending: Set to `True` while tasks to find or delete files are pending.
        disabled: Whether to disable this components' inputs.
    """
    selected: solara.Reactive[list[str]] = solara.use_reactive([])
    files = solara.use_reactive(
        files if files is not None else {},
        on_change=lambda fs: selected.set([f for f, s in fs.items() if s]),
    )

    @solara.lab.use_task(dependencies=None, raise_error=False)
    def find() -> None:
        files.set(dict.fromkeys(find_files(glob, subdir), True))

    @solara.lab.use_task(dependencies=None)
    def delete() -> None:
        deleted = set(delete_files(selected.get()))
        files.set({f: s for f, s in files.get().items() if f not in deleted})

    if pending is None:
        pending = solara.use_reactive(False)

    pending.set(find.pending or delete.pending)
    disabled = disabled or find.pending or delete.pending

    with solara.Row():
        solara.Button(
            label=f"Check for {subject}",
            on_click=find,
            color="primary",
            disabled=disabled,
        )
        solara.Button(
            label=f"Delete selected {subject}",
            on_click=delete,
            color="error",
            disabled=disabled or not selected.get(),
        )

    if find.not_called:
        return

    if not files.get():
        solara.Info(f"No {subject} found")
    else:
        solara.SelectMultiple(
            label=f"Select {subject} to delete",
            all_values=list(files.get()),
            # These have wrong type annotations :/
            values=selected,  # pyright: ignore[reportArgumentType]
            on_value=None,  # pyright: ignore[reportArgumentType]
            disabled=disabled,
        )


FindAndDeleteFiles(glob="*-Copy*.*", subject="duplicated files")
```

### Delete Data Files

Clear the `data` directory that contains exported data files.

```python
def is_file_older_than(path: str | Path, threshold: datetime) -> bool:
    fullpath = rootdir / path

    try:
        stat = fullpath.stat()
    except OSError:
        logger.exception("Failed to stat file", path=fullpath)
        return False

    mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
    return mtime < threshold
```

```python
@solara.component
def DeleteData() -> None:  # noqa: N802
    files: solara.Reactive[dict[str, bool]] = solara.use_reactive({})
    pending = solara.use_reactive(False)

    @solara.lab.use_task(dependencies=None)
    def select_old() -> None:
        threshold = datetime.now(tz=UTC) - timedelta(days=7)
        files.set(
            {
                file: is_file_older_than(file, threshold)
                for file, _ in files.get().items()
            }
        )

    FindAndDeleteFiles(
        glob="[!.]*",
        subdir="data",
        subject="data files",
        files=files,
        pending=pending,
        disabled=select_old.pending,
    )

    with solara.Row():
        solara.Button(
            label="Select only files older than 7 days",
            on_click=select_old,
            disabled=(not files.get() or pending.get() or select_old.pending),
        )


DeleteData()
```

## Advanced Features

Do not use these features unless you know what they do and understand their limitations.

### Switch Repository Branch

The default branch is `master` - this is where you find released notebooks.
Other branches might contain notebooks that are still in development and have
not been released yet.

Switching to another branch reverts all your local changes.
Same [guidelines](#Update-Project) apply as when updating.

```python
def strip_remote_prefix(shorthand: str) -> str:
    branch = repo.branches[shorthand]
    return shorthand.removeprefix(branch.remote_name + "/")
```

```python
def get_branch_timestamp(shorthand: str) -> datetime:
    branch = repo.branches[shorthand]

    commit = repo[branch.target]
    if not isinstance(commit, pygit2.Commit):
        raise ValueError  # noqa: TRY004

    return datetime.fromtimestamp(
        commit.commit_time,
        tz=timezone(timedelta(minutes=commit.commit_time_offset)),
    )
```

```python
def get_all_branches(repo: pygit2.Repository) -> list[str]:
    # Get branches sorted by last commit time.
    branches = sorted(
        (b for b in repo.branches if not b.endswith("/HEAD")),
        key=functools.cache(get_branch_timestamp),
        reverse=True,
    )

    # Strip remote prefixes from branch names.
    branches = [
        (strip_remote_prefix(b) if b in repo.branches.remote else b)
        for b in branches
    ]

    # Remove duplicates while preserving order.
    return list(dict.fromkeys(branches))
```

```python
@solara.component
def SwitchPage() -> None:  # noqa: N802
    branches = solara.use_memo(
        lambda: get_all_branches(repo),
        # Recompute after `git fetch`.
        dependencies=[fetch.latest],
    )

    initial_branch = solara.use_memo(lambda: repo.head.shorthand)
    current_branch = solara.use_reactive(initial_branch)
    selected_branch = solara.use_reactive(initial_branch)

    message = solara.use_reactive("")

    solara.Info(f"Currently on branch: {current_branch}")

    @solara.lab.use_task(dependencies=None, raise_error=False)
    async def switch() -> None:
        await run(["git", "switch", selected_branch.get()], check=True)
        await run(str(rootdir / "bootstrap.py"), check=True)
        current_branch.set(repo.head.shorthand)
        message.set(f"Switched to branch '{current_branch.get()}'")

    show_restore_dialog = solara.use_reactive(False)
    RestoreDialog(
        show=show_restore_dialog,
        then=switch,
    )

    with solara.Row(style={"align-items": "baseline"}):
        solara.Select(
            label="Branch",
            values=branches,
            value=selected_branch,
            on_value=lambda _: message.set(""),
        )
        solara.Button(
            label="Switch",
            disabled=(selected_branch.get() == current_branch.get()),
            color="primary",
            on_click=lambda: show_restore_dialog.set(True),
        )

    solara.ProgressLinear(switch.pending)
    if switch.error:
        solara.Error(str(switch.exception or "Error"))
    if message.get():
        solara.Info(message.get())


SwitchPage()
```

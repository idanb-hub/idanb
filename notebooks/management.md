# Project Management

Easy-to-use functions for managing this repository.

<details>
<summary>Maintainers</summary>

- **Milan Cermak** ([cermak@ics.muni.cz](mailto:cermak@ics.muni.cz))
- Stepan Dvorsky ([dvorsky@ics.muni.cz](mailto:dvorsky@ics.muni.cz))

</details>

```python
from __future__ import annotations

from idanb.nbinit import logger
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
import reacton
from ipymui import callback
from ipymui.components import mui

from idanb import meta, ui

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

repo = pygit2.Repository(meta.rootdir())
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
@reacton.component
def CommitLog(commits: list[pygit2.Commit]) -> None:  # noqa: N802
    with mui.Box():
        for commit in commits:
            mui.Typography(commit.message)
```

```python
new_commits_global = ui.create_global([])
repo_timestamp_global = ui.create_global(datetime.now(tz=UTC))
```

```python
@reacton.component
def FetchPage() -> None:  # noqa: N802
    with mui.Stack(direction="column", gap=1):
        new_commits, _ = ui.use_global(new_commits_global)

        @ui.use_task()
        async def fetch() -> None:
            await run("git fetch --verbose --prune", check=True)
            repo_timestamp_global.set(datetime.now(tz=UTC))
            if not is_rebase_safe():
                errmsg = "cannot update, git reset needed"
                raise RuntimeError(errmsg)
            commits = get_upstream_commits()
            new_commits_global.set(commits)

        # Automatically fetch on first render.
        reacton.use_memo(lambda: fetch(), dependencies=[])

        mui.Button(
            "Check Updates",
            onClick=lambda: fetch(),
            variant="contained" if not new_commits else "outlined",
            disabled=fetch.pending,
            fullWidth=True,
        )

        if fetch.pending:
            mui.LinearProgress()
        elif fetch.exception is not None:
            mui.Alert(str(fetch.exception), severity="error")

        if fetch.result is fetch.NO_RESULT:
            return

        if not new_commits:
            mui.Alert("You're up to date!", severity="success")
        else:
            with mui.Accordion():
                mui.AccordionSummary(
                    f"{len(new_commits)} new commits",
                    expandIcon=mui.icons.ExpandMore(),
                )
                with mui.AccordionDetails():
                    CommitLog(new_commits)
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


@reacton.component
def ChangedFilesList(files: dict[str, pygit2.enums.FileStatus]) -> None:  # noqa: N802
    with mui.Stack(direction="column"):
        for file, status in files.items():
            how = next(
                (msg for mask, msg in STATUS_MESSAGE.items() if status & mask),
                "unknown",
            )
            how += ":"

            mui.Typography(
                f"{how:12} {file}",
                sx=dict(
                    fontFamily="monospace",
                    whiteSpace="pre",
                ),
            )
```

```python
@reacton.component
def RestoreDialog(  # noqa: N802
    *,
    show: bool,
    on_close: T.Callable[[], None],
    then: T.Callable[[], None | T.Awaitable[None]] = lambda: None,
) -> None:
    """Show confirmation dialog and run `git restore`.

    The dialog lists changed files and asks the user for permission to revert
    the changes. If they click OK, changes are reverted and `then` is ran,
    otherwise nothing happens.

    Args:
        show: Whether to show the dialog or not.
        on_close: Called when dialog should close.
        then: Function to run after changes are reverted.
    """
    changes, set_changes = reacton.use_state({})

    def on_changes() -> None:
        # Skip dialog if there are no changes.
        if show and not changes:
            on_close()
            then()

    reacton.use_effect(on_changes, dependencies=[show, changes])

    if not ui.use_previous(show) and show:
        # Runs once every time dialog is opened (`show` changes to `True`).
        set_changes(repo.status(untracked_files="no"))

    @ui.use_task()
    async def restore() -> None:
        # The ":/" is magic pathspec for repository root.
        await run("git restore --staged --worktree :/", check=True)
        then()

    with mui.Dialog(
        open=show,
        onClose=lambda: on_close(),
    ):
        mui.DialogTitle("Revert local changes?")
        with mui.DialogContent():
            mui.Typography("If you click OK, these changes will be reverted:")
            ChangedFilesList(changes)
        with mui.DialogActions():
            mui.Button(
                "Cancel",
                onClick=lambda: on_close(),
            )
            mui.Button(
                "Revert",
                onClick=lambda: restore(),
                variant="contained",
            )
```

```python
@reacton.component
def RebasePage() -> None:  # noqa: N802
    with mui.Stack(direction="column", gap=1):
        new_commits, _ = ui.use_global(new_commits_global)

        @ui.use_task()
        async def update() -> None:
            # Rebase targets upstream by default (what we want).
            await run("git rebase", check=True)

            commits = get_upstream_commits()
            new_commits_global.set(commits)

            # Bootstrap script syncs dependencies and notebooks.
            await run(str(meta.rootdir() / "bootstrap.py"), check=True)

        dialog_open, set_dialog_open = reacton.use_state(False)
        RestoreDialog(
            show=dialog_open,
            on_close=lambda: set_dialog_open(False),
            then=update,
        )

        mui.Button(
            "Update",
            onClick=lambda: set_dialog_open(True),
            disabled=update.pending or not new_commits,
            variant="contained",
            fullWidth=True,
        )

        if update.pending:
            mui.LinearProgress()
        if update.exception is not None:
            mui.Alert(str(update.exception), severity="error")
```

```python
@reacton.component
def UpdatePage() -> None:  # noqa: N802
    with mui.Stack(direction="column", gap=1):
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
    rootdir = meta.rootdir()
    startdir = rootdir / subdir
    return (
        str(path.relative_to(rootdir))
        for path in startdir.rglob(glob)
        if path.is_file()
    )


def delete_files(files: T.Iterable[str]) -> T.Iterable[str]:
    for path in files:
        fullpath = meta.rootdir() / path
        try:
            fullpath.unlink(missing_ok=True)
        except OSError:
            logger.exception("Failed to delete file", path=path)
        else:
            logger.info("File deleted", path=path)
            yield path
```

```python
@reacton.component
def FindAndDeleteFiles(  # noqa: N802, PLR0913
    *,
    glob: str,
    subdir: str = ".",
    files: dict[str, bool] | None = None,
    on_files: T.Callable[[dict[str, bool]], None] | None = None,
    subject: str = "files",
    pending: bool = False,
    on_pending: T.Callable[[bool], None] | None = None,
    disabled: bool = False,
) -> None:
    """Component for finding, selecting, and deleting files.

    Args:
        glob: Glob pattern of files to find.
        subdir: Path relative to repository root to search.
        files: Dictionary holding found files and whether they are selected.
        on_files: Called when `files` should change.
        subject: Human-readable summary of `glob` (shown in UI).
        pending: Whether task to find or delete files is pending.
        on_pending: Called when `pending` should change.
        disabled: Whether to disable this components' inputs.
    """
    files, set_files = ui.use_state_from(files or {}, on_files)

    selected = [f for f, s in files.items() if s]

    @ui.use_task()
    async def find() -> None:
        set_files(dict.fromkeys(find_files(glob, subdir), True))

    @ui.use_task()
    async def delete() -> None:
        deleted = set(delete_files(selected))
        set_files({f: s for f, s in files.items() if f not in deleted})

    pending, set_pending = ui.use_state_from(pending, on_pending)

    set_pending(find.pending or delete.pending)
    disabled = disabled or find.pending or delete.pending

    with mui.Stack(direction="row", spacing=1):
        mui.Button(
            f"Check for {subject}",
            onClick=lambda: find(),
            variant="contained",
            disabled=disabled,
        )
        mui.Button(
            f"Delete selected {subject}",
            onClick=lambda: delete(),
            variant="contained",
            color="error",
            disabled=disabled or not selected,
        )

    if find.not_called:
        return

    if not files:
        mui.Alert(f"No {subject} found", severity="info")
    else:

        def update_selection(selected: set[str]) -> None:
            set_files({f: (f in selected) for f in files})

        with mui.Select(
            label=f"Select {subject} to delete",
            multiple=True,
            disabled=disabled,
            fullWidth=True,
            value=selected,
            onChange=callback("$[0].target.value")(
                lambda value: update_selection(set(value))
            ),
        ):
            for file in files:
                mui.MenuItem(file, value=file)


FindAndDeleteFiles(glob="*-Copy*.*", subject="duplicated files")
```

### Delete Data Files

Clear the `data` directory that contains exported data files.

```python
def is_file_older_than(path: str | Path, threshold: datetime) -> bool:
    fullpath = meta.rootdir() / path

    try:
        stat = fullpath.stat()
    except OSError:
        logger.exception("Failed to stat file", path=fullpath)
        return False

    mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
    return mtime < threshold
```

```python
@reacton.component
def DeleteData() -> None:  # noqa: N802
    files, set_files = reacton.use_state({})
    pending, set_pending = reacton.use_state(False)

    @ui.use_task()
    async def select_old() -> None:
        threshold = datetime.now(tz=UTC) - timedelta(days=7)
        set_files(
            {
                file: is_file_older_than(file, threshold)
                for file, _ in files.items()
            }
        )

    FindAndDeleteFiles(
        glob="[!.]*",
        subdir="data",
        subject="data files",
        files=files,
        on_files=set_files,
        pending=pending,
        on_pending=set_pending,
        disabled=select_old.pending,
    )

    with mui.Stack(direction="row", spacing=1):
        mui.Button(
            "Select only files older than 7 days",
            onClick=lambda: select_old(),
            variant="contained",
            disabled=(not files or pending or select_old.pending),
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
@reacton.component
def SwitchPage() -> None:  # noqa: N802
    repo_timestamp, _ = ui.use_global(repo_timestamp_global)

    branches = reacton.use_memo(
        lambda: get_all_branches(repo),
        # Recompute after `git fetch`.
        dependencies=[repo_timestamp],
    )

    initial_branch = reacton.use_memo(lambda: repo.head.shorthand)
    current_branch, set_current_branch = reacton.use_state(initial_branch)
    selected_branch, set_selected_branch = reacton.use_state(initial_branch)

    message, set_message = reacton.use_state("")

    mui.Alert(f"Currently on branch: {current_branch}")

    @ui.use_task()
    async def switch() -> None:
        await run(["git", "switch", selected_branch], check=True)
        await run(str(meta.rootdir() / "bootstrap.py"), check=True)
        set_current_branch(repo.head.shorthand)
        set_message(f"Switched to branch '{current_branch}'")

    dialog_open, set_dialog_open = reacton.use_state(False)
    RestoreDialog(
        show=dialog_open,
        on_close=lambda: set_dialog_open(False),
        then=switch,
    )

    with mui.Stack(direction="row", spacing=1, alignItems="baseline"):
        with mui.Select(
            label="Branch",
            fullWidth=True,
            value=selected_branch,
            onChange=callback("$[0].target.value")(
                lambda value: (set_selected_branch(value), set_message("")),
            ),
        ):
            for branch in branches:
                mui.MenuItem(branch, value=branch)
        mui.Button(
            "Switch",
            disabled=(selected_branch == current_branch),
            variant="contained",
            onClick=lambda: set_dialog_open(True),
        )

    if switch.pending:
        mui.LinearProgress()
    if switch.exception is not None:
        mui.Alert(str(switch.exception), severity="error")
    if message:
        mui.Alert(message)


SwitchPage()
```

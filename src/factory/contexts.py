"""The Run Context Store: Run Contexts as folders of local files on the Factory's image.

Not a port (ADR 0013): create a Context, write into it, give a path for the Repo Host to check out
into, and hand the same Context back. The layout inside a Context is in docs/specs/0004.
"""

import re
import shutil
from pathlib import Path

PathLike = str | Path


def slug(text: str) -> str:
    """A name safe in paths: a Task id such as `repo/12` becomes `repo-12`."""
    return re.sub(r"[^a-z0-9_.-]+", "-", text.lower()).strip("-.")


class Context:
    def __init__(self, path: PathLike) -> None:
        self.dir = Path(path)

    def __str__(self) -> str:
        return str(self.dir)

    def path(self, name: str) -> Path:
        """Where `name` is (or will be) inside the Context, e.g. for a checkout."""
        return self.dir / name

    def write(self, name: str, text: str) -> None:
        target = self.path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def remove(self, name: str) -> None:
        shutil.rmtree(self.path(name), ignore_errors=True)

    def mkdir(self, name: str) -> None:
        self.path(name).mkdir(parents=True, exist_ok=True)

    def copy(self, source: PathLike, name: str, *, executable: bool = False) -> None:
        """Copy a file or folder of the core's resources into the Context."""
        target = self.path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if Path(source).is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            shutil.copy(source, target)
            if executable:
                target.chmod(0o755)


class ContextStore:
    def __init__(self, root: PathLike) -> None:
        self.root = Path(root)

    def location(self, *key: str) -> Path:
        return self.root.joinpath(*(slug(part) for part in key))

    def create(self, *key: str) -> Context:
        """A fresh, empty Context; one left from an earlier start of the same key is discarded."""
        path = self.location(*key)
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True)
        return Context(path)

    def get(self, *key: str) -> Context:
        """The same Context an earlier `create` made, with everything the Runner added to it."""
        return Context(self.location(*key))

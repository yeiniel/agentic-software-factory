"""The Run Context Store: Run Contexts as folders of local files on the Factory's image.

Not a port (ADR 0013): create a Context, write into it, give a path for the Repo Host to check out
into, and hand the same Context back. The layout inside a Context is in docs/specs/0004.
"""
import re
import shutil
from pathlib import Path


def slug(text):
    """A name safe in paths: a Task id such as `repo/12` becomes `repo-12`."""
    return re.sub(r"[^a-z0-9_.-]+", "-", text.lower()).strip("-.")


class Context:
    def __init__(self, path):
        self.dir = Path(path)

    def __str__(self):
        return str(self.dir)

    def path(self, name):
        """Where `name` is (or will be) inside the Context, e.g. for a checkout."""
        return self.dir / name

    def write(self, name, text):
        target = self.path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def remove(self, name):
        shutil.rmtree(self.path(name), ignore_errors=True)

    def mkdir(self, name):
        self.path(name).mkdir(parents=True, exist_ok=True)

    def copy(self, source, name, executable=False):
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
    def __init__(self, root):
        self.root = Path(root)

    def location(self, *key):
        return self.root.joinpath(*(slug(part) for part in key))

    def create(self, *key):
        """A fresh, empty Context; one left from an earlier start of the same key is discarded."""
        path = self.location(*key)
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True)
        return Context(path)

    def get(self, *key):
        """The same Context an earlier `create` made, with everything the Runner added to it."""
        path = self.location(*key)
        if not path.is_dir():
            raise FileNotFoundError(f"no Run Context at {path}")
        return Context(path)

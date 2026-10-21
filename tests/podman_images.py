"""Images the tests build are labelled with a per-session token, so a run neither reuses nor leaks an image.

The Runner tags an image by the content of its Containerfile; a unique label makes every session build its own
(the first test pays, the others reuse it), and the session removes them when it ends.
"""

import shutil
import subprocess
import uuid

TOKEN = uuid.uuid4().hex
CONTAINERFILE = f"FROM docker.io/library/alpine\nRUN apk add --no-cache git make\nLABEL asf.test={TOKEN}\n"


def remove_images() -> None:
    if not shutil.which("podman"):
        return
    ids = subprocess.run(
        ["podman", "images", "-q", "--filter", f"label=asf.test={TOKEN}"], capture_output=True, text=True, check=False
    ).stdout.split()
    if ids:
        subprocess.run(["podman", "rmi", "-f", *ids], capture_output=True, check=False)

"""Building the Environment's image for a Run Context (internal to the Runner).

The Containerfile at the root of the Context's `cwd` is built first, with `cwd` as the build context,
and must provide `git` and `make`. For the agentic type the agent harness layer (images/agent/ or
$ASF_IMAGES_DIR/agent/) is built on top. Images are tagged by the Containerfile's content (and the
layer's content), and an existing image is reused.

$ASF_BUILD_SECCOMP_PROFILE, if set, is the seccomp profile for build steps (a Podman client in a container
sends its own default path, which the host's Podman may not have).
"""
import hashlib
import os
import subprocess
from pathlib import Path

from .common import Failure, podman


def layer_dir():
    root = os.environ.get("ASF_IMAGES_DIR") or Path(__file__).resolve().parent.parent / "images"
    return Path(root) / "agent"


def digest(*parts):
    """Short hash, so changed content means a new image."""
    h = hashlib.sha256()
    for part in parts:
        h.update(part)
    return h.hexdigest()[:12]


def layer_digest(directory):
    return digest(*(str(p.relative_to(directory)).encode() + p.read_bytes()
                    for p in sorted(p for p in directory.rglob("*") if p.is_file())))


def build_args():
    profile = os.environ.get("ASF_BUILD_SECCOMP_PROFILE")
    return ["--security-opt", f"seccomp={profile}"] if profile else []


def exists(tag):
    return podman("image", "exists", tag, check=False).returncode == 0


def build(*args, timeout):
    try:
        podman("build", "-q", *build_args(), *args, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Failure(f"image build exceeded {timeout:g}s") from None


def build_base(cwd, tag, timeout):
    containerfile = cwd / "Containerfile"
    build("-t", tag, "-f", str(containerfile), str(cwd), timeout=timeout)
    probe = podman("run", "--rm", "--entrypoint", "sh", tag, "-c",
                   "command -v git > /dev/null || exit 3; command -v make > /dev/null || exit 4",
                   check=False)
    if probe.returncode:
        podman("rmi", "-f", tag, check=False)
        missing = {3: "git", 4: "make"}.get(probe.returncode)
        raise Failure(f"the image built from {containerfile} "
                      + (f"lacks `{missing}`" if missing else f"cannot run `sh`: {probe.stderr.strip()}")
                      + "; it must provide git and make")


def image(cwd, agentic, timeout):
    """The image for `cwd`'s Containerfile, built if it is not there yet."""
    cwd = Path(cwd)
    if not (cwd / "Containerfile").is_file():
        raise Failure(f"{cwd} has no Containerfile at its root")
    base = f"localhost/asf-base:{digest((cwd / 'Containerfile').read_bytes())}"
    if not exists(base):
        build_base(cwd, base, timeout)
    if not agentic:
        return base
    layer = layer_dir()
    tag = f"localhost/asf-agent:{base.split(':')[1]}-{layer_digest(layer)}"
    if not exists(tag):
        build("--build-arg", f"BASE={base}", "-t", tag, str(layer), timeout=timeout)
    return tag

"""Environment Builder against real Podman, with the harness layers stubbed (no model, no Pi)."""
import subprocess

from helpers import CONTAINERFILE, needs_podman

pytestmark = needs_podman


def podman(*args):
    return subprocess.run(["podman", *args], capture_output=True, text=True)


def test_the_agent_image_layers_the_harness_on_the_repos_image(exe, repo):
    commit = repo({"README": "x", "Containerfile": CONTAINERFILE})
    image = exe("environment-builder").ok("build", repo="r", commit=commit, purpose="agent")["image"]
    done = podman("run", "--rm", "--entrypoint", "sh", image, "-c", "command -v git && command -v make && ls /entrypoint.sh")
    assert done.returncode == 0, done.stderr


def test_the_repo_is_built_at_the_given_commit(exe, repo, tmp_path):
    first = repo({"Containerfile": CONTAINERFILE + "RUN echo one > /which\n"})
    from gitrepohost import commit_files
    commit_files(tmp_path / "git" / "r.git", {"Containerfile": CONTAINERFILE + "RUN echo two > /which\n"}, "two")
    image = exe("environment-builder").ok("build", repo="r", commit=first, purpose="integrator")["image"]
    assert podman("run", "--rm", "--entrypoint", "cat", image, "/which").stdout == "one\n"


def test_a_repo_without_a_containerfile_is_reported(exe, repo):
    commit = repo({"README": "x"})
    done = exe("environment-builder").run("build", repo="r", commit=commit, purpose="agent")
    assert done.returncode != 0 and "no Containerfile" in done.stderr


def test_an_image_without_make_is_reported_and_not_kept(exe, repo):
    commit = repo({"Containerfile": "FROM docker.io/library/alpine\nRUN apk add --no-cache git\n"})
    done = exe("environment-builder").run("build", repo="r", commit=commit, purpose="agent")
    assert done.returncode != 0 and "lacks `make`" in done.stderr
    assert podman("image", "exists", f"localhost/asf-base-r:{commit[:12]}").returncode != 0


def test_an_image_without_git_is_reported(exe, repo):
    commit = repo({"Containerfile": "FROM docker.io/library/alpine\nRUN apk add --no-cache make\n"})
    done = exe("environment-builder").run("build", repo="r", commit=commit, purpose="agent")
    assert done.returncode != 0 and "lacks `git`" in done.stderr


def test_a_second_build_reuses_the_cached_images(exe, repo, tmp_path):
    commit = repo({"Containerfile": CONTAINERFILE})
    log = tmp_path / "podman.log"
    wrapper = tmp_path / "podman"
    wrapper.write_text(f'#!/bin/sh\necho "$1" >> {log}\nexec podman "$@"\n')
    wrapper.chmod(0o755)
    builder = exe("environment-builder")
    builder.env["PODMAN"] = str(wrapper)
    first = builder.ok("build", repo="r", commit=commit, purpose="agent")
    log.write_text("")
    assert builder.ok("build", repo="r", commit=commit, purpose="agent") == first
    assert "build" not in log.read_text().split()

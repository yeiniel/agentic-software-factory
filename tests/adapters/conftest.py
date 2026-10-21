"""Fixtures for the real Adapters' own behaviour tests."""

import os

import pytest

from helpers import STUB_IMAGES, Exe

import gitrepohost


@pytest.fixture
def env(tmp_path):
    return {
        **os.environ,
        "REPO_HOST_URL": str(tmp_path / "git"),
        "ADAPTER_CACHE": str(tmp_path / "cache"),
        "RECORDS_DIR": str(tmp_path / "records"),
        "RUNNER_ROOT": str(tmp_path / "runner"),
        "ASF_IMAGES_DIR": str(STUB_IMAGES),
        "ASF_MODEL_ENDPOINT": "http://model:8080/v1",
        "ASF_MODEL_NAME": "qwen",
        "ASF_MODEL_CONTEXT_WINDOW": "98304",
    }


@pytest.fixture
def exe(env):
    return lambda name: Exe(name, env)


@pytest.fixture
def repo(tmp_path):
    """Seed repository `r`; returns a function to add a repo with the given files and give its main."""

    def make(files, name="r"):
        gitrepohost.seed_repo(tmp_path / "git", name, files)
        return gitrepohost.git("--git-dir", str(tmp_path / "git" / f"{name}.git"), "rev-parse", "main")

    return make

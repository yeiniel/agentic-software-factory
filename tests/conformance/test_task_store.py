import pytest


@pytest.fixture
def store(adapter):
    return adapter("task-store")


def test_get_prompt_returns_the_tasks_prompt(store):
    result = store.ok("get-prompt", task=store.fixture["task"])
    assert result == {"prompt": store.fixture["prompt"]}


def test_get_prompt_of_an_unknown_task_fails(store):
    store.fails("get-prompt", task="no-such-task")


@pytest.mark.parametrize("status", ["todo", "running", "done", "blocked"])
def test_set_status_accepts_the_four_statuses(store, status):
    assert store.ok("set-status", task=store.fixture["task"], status=status) == {}


def test_set_status_accepts_the_documented_bodies(store):
    task = store.fixture["task"]
    store.ok("set-status", {"commit": "abc123"}, task=task, status="done")
    store.ok("set-status", {"history": [{"run": 1}], "reason": "infrastructure"}, task=task, status="blocked")


def test_set_status_rejects_an_unknown_status(store):
    store.fails("set-status", task=store.fixture["task"], status="exploded")


def test_unknown_operation_fails(store):
    store.fails("no-such-op")

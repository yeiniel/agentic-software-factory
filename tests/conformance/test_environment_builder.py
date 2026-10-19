import pytest


@pytest.fixture
def builder(adapter):
    return adapter("environment-builder")


def build(builder, purpose):
    return builder.ok("build", repo=builder.fixture["repo"], commit=builder.fixture["commit"],
                      purpose=purpose)["image"]


@pytest.mark.parametrize("purpose", ["agent", "integrator"])
def test_build_returns_an_image(builder, purpose):
    assert build(builder, purpose)


def test_build_is_cached_per_repo_and_commit(builder):
    assert build(builder, "agent") == build(builder, "agent")


def test_the_two_purposes_get_different_images(builder):
    assert build(builder, "agent") != build(builder, "integrator")


def test_an_unknown_purpose_fails(builder):
    builder.fails("build", repo=builder.fixture["repo"], commit=builder.fixture["commit"], purpose="wizard")


def test_unknown_operation_fails(builder):
    builder.fails("no-such-op")

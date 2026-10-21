"""An Adapter's command line and JSON are its wire: whatever arrives, it succeeds or refuses cleanly."""

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

CONFIG = settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
JSON = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(max_size=12),
    lambda inner: st.lists(inner, max_size=3) | st.dictionaries(st.text(max_size=8), inner, max_size=3),
    max_leaves=10,
)


def clean(done):
    """Exit status 0 (done) or 1 (refused, said on stderr); never a crash with a traceback."""
    assert done.returncode in (0, 1), done.stderr
    assert "Traceback" not in done.stderr


@CONFIG
@given(
    stream=st.text(alphabet=st.characters(exclude_characters="\x00", exclude_categories=["Cs"]), max_size=20), body=JSON
)
def test_records_accepts_or_refuses_any_stream_and_body(exe, stream, body):
    clean(exe("records").run("append", body, stream=stream))


@CONFIG
@given(
    stream=st.text(alphabet=st.characters(exclude_characters="\x00", exclude_categories=["Cs"]), max_size=20), body=JSON
)
def test_records_otlp_accepts_or_refuses_any_stream_and_body(exe, stream, body):
    clean(exe("records-otlp").run("append", body, stream=stream))

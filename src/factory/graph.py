"""The Graph: a folder holding `graph.json` and everything it names, loaded and checked once (ADR 0020, spec 0008).

Every rejection is a `GraphError` raised by `load`, so the Factory refuses to start on an invalid Graph.
"""

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match  # pyright: ignore[reportUnknownVariableType]

from .adapters import Json

RESOURCES = Path(__file__).parent / "resources"  # the default Graph
SCHEMA: Json = json.loads((Path(__file__).parent / "graph.schema.json").read_text())


class GraphError(Exception):
    pass


class Violation(Protocol):
    """What the Graph needs of a jsonschema error, which the library leaves untyped."""

    absolute_path: Iterable[str | int]
    message: str


def load(folder: Path) -> Json:
    data: Json = json.loads((folder / "graph.json").read_text())
    errors = list(Draft202012Validator(SCHEMA).iter_errors(data))  # pyright: ignore[reportUnknownMemberType]
    error = cast("Violation | None", best_match(errors))
    if error:
        where = ".".join(str(part) for part in error.absolute_path)
        raise GraphError(f"{where}: {error.message}")
    return data

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


def enclosing(states: dict[str, Json]) -> dict[str, set[str]]:
    """Each state -> the compound states that hold it, however deep."""
    holder = {child: name for name, s in states.items() for child in [*s.get("contains", []), *s.get("regions", [])]}
    chains: dict[str, set[str]] = {}
    for name in states:
        chains[name], at = set(), name
        while at in holder:
            at = holder[at]
            chains[name].add(at)
    return chains


def find_cycle(states: dict[str, Json]) -> list[str] | None:
    """A cycle among the transitions that spend no attempt budget.

    A transition to an enclosing loop is the next attempt of that loop, and its attempts are finite; `$exit` leaves.
    Any other transition goes on, so a cycle of those never ends.
    """
    holders = enclosing(states)
    goes_to = {
        name: [t["to"] for t in s.get("transitions", []) if t["to"] != "$exit" and t["to"] not in holders[name]]
        for name, s in states.items()
    }

    def walk(name: str, path: list[str]) -> list[str] | None:
        if name in path:
            return [*path[path.index(name) :], name]
        return next(filter(None, (walk(to, [*path, name]) for to in goes_to.get(name, []))), None)

    return next(filter(None, (walk(name, []) for name in states)), None)


def load(folder: Path) -> Json:
    data: Json = json.loads((folder / "graph.json").read_text())
    errors = list(Draft202012Validator(SCHEMA).iter_errors(data))  # pyright: ignore[reportUnknownMemberType]
    error = cast("Violation | None", best_match(errors))
    if error:
        where = ".".join(str(part) for part in error.absolute_path)
        raise GraphError(f"{where}: {error.message}")
    if cycle := find_cycle(data["states"]):
        raise GraphError("a cycle that no attempt budget bounds: " + " -> ".join(cycle))
    return data

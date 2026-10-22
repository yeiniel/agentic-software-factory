"""The Graph: a folder holding `graph.json` and everything it names, loaded and checked once (ADR 0020, spec 0008).

Every rejection is a `GraphError` raised by `load`, so the Factory refuses to start on an invalid Graph.
"""

import json
import re
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


def outcomes(state: Json) -> list[str]:
    """What a state can end with: `red:<check>` is a failed check, which a plain `red` transition also covers."""
    match state["type"]:
        case "agentic":
            return ["green", "crashed", "timed-out"]
        case "deterministic":
            return ["green", "timed-out", *(f"red:{check}" for check in state["checks"])]
        case "loop":
            return ["exhausted"]
        case "parallel":
            return ["green"]
        case "publish":
            return ["advanced", "main-moved"]
        case _:
            return []


def check_names(data: Json) -> None:
    """Everything the Graph points at is a state it defines."""
    states: dict[str, Json] = data["states"]
    for name in (data["start"], data["error"]):
        if name not in states:
            raise GraphError(f"{name} is not a state")
    for name, state in states.items():
        for child in [state.get("entry"), *state.get("contains", []), *state.get("regions", [])]:
            if child is not None and child not in states:
                raise GraphError(f"{name}: {child} is not a state")
        for transition in state.get("transitions", []):
            if transition["to"] != "$exit" and transition["to"] not in states:
                raise GraphError(f"{name}: {transition['on']} goes to {transition['to']}, which is not a state")


def unreached(data: Json) -> list[str]:
    """The states that neither `start` nor `error` leads to, through containment or a transition."""
    states: dict[str, Json] = data["states"]
    reached: set[str] = set()
    todo = [data["start"], data["error"]]
    while todo:
        name = todo.pop()
        if name not in reached:
            reached.add(name)
            state = states.get(name, {})
            todo += [*state.get("contains", []), *state.get("regions", [])]
            todo += [t["to"] for t in state.get("transitions", []) if t["to"] != "$exit"]
    return [name for name in states if name not in reached]


def check_schema(data: Json) -> None:
    errors = list(Draft202012Validator(SCHEMA).iter_errors(data))  # pyright: ignore[reportUnknownMemberType]
    error = cast("Violation | None", best_match(errors))
    if error:
        where = ".".join(str(part) for part in error.absolute_path)
        raise GraphError(f"{where}: {error.message}")


def check_outcomes(states: dict[str, Json]) -> None:
    for name, state in states.items():
        handled = {t["on"] for t in state.get("transitions", [])}
        for outcome in outcomes(state):
            if outcome not in handled and outcome.split(":")[0] not in handled:
                raise GraphError(f"{name}: no transition for {outcome}")


def named_files(state: Json) -> list[str]:
    """The paths a state names: what it hands to its executor, and the Feedback messages of its transitions."""
    own = [state[key] for key in ("instruction", "system-prompt", "skills", "script") if key in state]
    return own + [t["feedback"]["message"] for t in state.get("transitions", []) if "feedback" in t]


def check_files(folder: Path, states: dict[str, Json]) -> None:
    for name, state in states.items():
        for relative in named_files(state):
            if not (folder / relative).exists():
                raise GraphError(f"{name}: {relative} is not in the Graph folder")


def check_messages(folder: Path, states: dict[str, Json]) -> None:
    """A Feedback message may use only `{check}` and `{output}`: it can never name another Agent's branch."""
    for state in states.values():
        for transition in state.get("transitions", []):
            if "feedback" in transition:
                message = transition["feedback"]["message"]
                for placeholder in re.findall(r"\{([^{}]*)\}", (folder / message).read_text()):
                    if placeholder not in ("check", "output"):
                        raise GraphError(
                            f"{message}: {{{placeholder}}} is not a placeholder; use {{check}} and {{output}}"
                        )


def branches_read(state: Json) -> list[str]:
    """The branches a state reads: a workspace or an input that is the branch of another output, or a publish."""
    sources = [state["workspace"]] if "workspace" in state else list(state.get("inputs", {}).values())
    named = [source["branch-of"] for source in sources if source != "base"]
    return named + ([state["branch"]] if state["type"] == "publish" else [])


def check_timeouts(states: dict[str, Json], config: Json) -> None:
    """A timeout that is a name must be a key of the Factory's config."""
    for name, state in states.items():
        if isinstance(state.get("timeout"), str) and state["timeout"] not in config:
            raise GraphError(f"{name}: the timeout {state['timeout']} is not in the Factory's config")


def check_start(data: Json) -> None:
    """The start loop's attempts are the Runs, and a Task ends in a status, so its states never `$exit`."""
    states: dict[str, Json] = data["states"]
    if [name for name, state in states.items() if state.get("runs")] != [data["start"]]:
        raise GraphError("`runs` marks the start loop, and only the start loop: its attempts are the Runs")
    for name, state in states.items():
        for child in state.get("contains", []):
            if states[child]["type"] == "loop":
                raise GraphError(f"{name}: {child} is a loop inside a loop; a loop sits in a parallel state")
    for name in states[data["start"]]["contains"]:
        for transition in states[name].get("transitions", []):
            if transition["to"] == "$exit":
                raise GraphError(f"{name}: {transition['on']} goes to $exit, which would end the start loop")


def check_environments(states: dict[str, Json]) -> None:
    """The Environment is built from the Containerfile of one of the state's own inputs."""
    for name, state in states.items():
        if "environment" in state and state["environment"] not in state["inputs"]:
            raise GraphError(f"{name}: the environment {state['environment']} is not one of its inputs")


def check_branches(states: dict[str, Json]) -> None:
    made = {s["output"]["branch"] for s in states.values() if "output" in s}
    for name, state in states.items():
        for branch in branches_read(state):
            if branch not in made:
                raise GraphError(f"{name}: reads the branch {branch}, which no Activity makes")


def check_targets(states: dict[str, Json]) -> None:
    holders = enclosing(states)
    roles = {s["role"] for s in states.values() if s["type"] == "agentic"}
    for name, state in states.items():
        for transition in state.get("transitions", []):
            target = transition["to"]
            where = f"{name}: {transition['on']} goes to {target}"
            for reset in transition.get("reset", []):
                if states.get(reset, {}).get("type") != "loop":
                    raise GraphError(f"{where}, resetting {reset}, which is not a loop in the Graph")
            feedback = transition.get("feedback")
            if feedback and feedback["for"] not in roles:
                raise GraphError(f"{where}, with Feedback for {feedback['for']}, a role the Graph does not run")
            if states.get(target, {}).get("status") == "done" and state["type"] != "publish":
                raise GraphError(f"{where}, which is done; only publish may")
            if target in holders[name] and states[target]["type"] != "loop":
                raise GraphError(f"{where}, which is not a loop and has no attempts")


class Graph:
    """A checked Graph: what the interpreter reads."""

    def __init__(self, folder: Path, version: str, data: Json) -> None:
        self.folder = folder
        self.version = version
        self.start: str = data["start"]
        self.error: str = data["error"]  # the blocked status an Adapter error or a malformed verdict leads to
        self.states: dict[str, Json] = data["states"]
        self.roles = list(dict.fromkeys(s["role"] for s in self.states.values() if s["type"] == "agentic"))

    def read(self, relative: str) -> str:
        return (self.folder / relative).read_text().strip()


def load(folder: Path, version: str, config: Json) -> Graph:
    data: Json = json.loads((folder / "graph.json").read_text())
    check_schema(data)
    check_names(data)
    if orphans := unreached(data):
        raise GraphError(f"{orphans[0]}: no transition reaches this state")
    check_files(folder, data["states"])
    check_messages(folder, data["states"])
    check_branches(data["states"])
    check_start(data)
    check_environments(data["states"])
    check_timeouts(data["states"], config)
    check_outcomes(data["states"])
    check_targets(data["states"])
    if cycle := find_cycle(data["states"]):
        raise GraphError("a cycle that no attempt budget bounds: " + " -> ".join(cycle))
    return Graph(folder, version, data)

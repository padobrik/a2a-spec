"""Types a consumer's parameters are annotated with, shared by the Python and TypeScript readers."""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from agent_handshake.infer.paths import ITEMS, dotted

T = TypeVar("T")


class Read(Protocol):
    """A field read: its key path and line (``FieldRead``)."""

    @property
    def path(self) -> tuple[str, ...]: ...

    @property
    def line(self) -> int: ...


@dataclass(frozen=True)
class TypeShape:
    """A structured type and its declared fields."""

    name: str
    fields: dict[str, FieldShape] = field(default_factory=dict)


@dataclass(frozen=True)
class FieldShape:
    """One declared field: required or not, and its object or item type when known."""

    required: bool
    nested: TypeShape | None = None
    item: TypeShape | None = None


@dataclass(frozen=True)
class Annotation:
    """What a parameter's annotation tells about the value.

    ``shape`` is the resolved type of the value, or of each item when
    ``items`` is true. ``wrapper`` names the attribute of a framework result
    that holds the output (``final_output`` of ``RunResult``). ``present`` is
    false for a parameter without an annotation.
    """

    shape: TypeShape | None = None
    items: bool = False
    mapping: bool = False
    primitive: bool = False
    present: bool = False
    wrapper: str | None = None


def choose_param(
    described: Sequence[tuple[T, Annotation]],
    keys: Collection[str] | None,
    reads_of: Callable[[T, Annotation], set[str]],
    output: str | None = None,
) -> tuple[T, Annotation] | None:
    """The parameter that holds the producer's output, or None when none can.

    Without ``keys`` (the producer's output keys), the first parameter with a
    resolved type wins, else the first that is not a plain string or number.

    With ``keys``, a parameter matches when its type declares most of the
    keys, or, for a type that cannot be resolved (or a framework result), when
    the fields the code reads from it include one of the keys. The best match
    wins. When every parameter can be judged and none matches, the producer's
    data is not a parameter (it may come from shared state): None. A
    parameter without an annotation, or annotated as a dict, cannot be
    judged; it is then taken as before.

    ``output`` is ``"text"`` or ``"list"`` when the producer's output is not
    an object. Text has no fields, so a parameter the code reads fields from
    does not hold it; a list's fields are read per item, so only a parameter
    annotated as a list, or one read for no fields, can hold it.
    """
    if output in ("text", "list"):
        for param, annotation in described:
            if annotation.mapping or (annotation.shape and not annotation.items):
                continue  # a dict or a single object is neither text nor a list
            if output == "list" and annotation.items:
                return param, annotation
            if not reads_of(param, annotation):
                return param, annotation
        return None
    candidates = [(p, a) for p, a in described if not a.primitive] or list(described)
    if not keys:
        typed = [(p, a) for p, a in candidates if a.shape is not None or a.wrapper]
        return (typed or candidates)[0]
    wanted = set(keys)
    scores: list[tuple[int, int]] = []  # (score, -index) of matching parameters
    unjudged: list[int] = []
    for index, (param, annotation) in enumerate(candidates):
        if annotation.shape is not None:
            covered = len(wanted & set(annotation.shape.fields))
            if 2 * covered > len(wanted):
                scores.append((covered, -index))
        elif annotation.present and not annotation.mapping:
            overlap = len(wanted & reads_of(param, annotation))
            if overlap:
                scores.append((overlap, -index))
        else:
            unjudged.append(index)
    if scores:
        return candidates[-max(scores)[1]]
    if unjudged:
        return candidates[unjudged[0]]
    return None


def output_kind(outputs: Sequence[object]) -> str | None:
    """``"text"`` or ``"list"`` when every recorded output is one, else None."""
    if outputs and all(isinstance(o, str) for o in outputs):
        return "text"
    if outputs and all(isinstance(o, list) for o in outputs):
        return "list"
    return None


def no_matching_param(
    function: str,
    path: object,
    params: Sequence[str],
    keys: Collection[str] | None,
    output: str | None = None,
) -> str:
    """The error when no parameter of ``function`` holds the producer's output."""
    if output in ("text", "list"):
        what = "text" if output == "text" else "a list"
        reason = f": its output is {what}, and every parameter is read as an object"
    else:
        shown = ", ".join(sorted(keys or [])[:8])
        reason = f" (keys: {shown}): none has a type that declares these keys or reads them"
    return (
        f"No parameter of '{function}' in {path} ({', '.join(params)}) holds the "
        f"producer's output{reason}. Check --producer, or the data may come from shared state."
    )


def undeclared(reads: Sequence[Read], shape: TypeShape | None) -> list[str]:
    """Warnings for reads of fields the parameter's type does not declare."""
    warnings: list[str] = []
    reported: set[str] = set()
    for read in reads:
        current = shape
        for depth, key in enumerate(read.path):
            if key == ITEMS:
                continue  # the item type was taken with the list field
            if current is None or not current.fields:
                break
            declared = current.fields.get(key)
            if declared is None:
                label = dotted(read.path[: depth + 1])
                if label not in reported:
                    reported.add(label)
                    warnings.append(
                        f"line {read.line}: '{label}' is not a field of {current.name}; "
                        "the inferred contract may be incomplete"
                    )
                break
            current = declared.nested or declared.item
    return warnings

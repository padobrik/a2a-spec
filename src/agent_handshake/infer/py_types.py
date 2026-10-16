"""What a Python parameter annotation says about the producer's output.

A consumer such as ``def handle(query: str, report: Report)`` names the
producer's type in an annotation. This module finds that type (a Pydantic
model, a TypedDict or a dataclass) in the same file or in a module the file
imports from the same project, and lists its fields. The code is parsed, never
imported.
"""

from __future__ import annotations

import ast
from pathlib import Path

from agent_handshake.infer.shapes import Annotation, FieldShape, TypeShape

# Annotations of a dict-like input: keys are read with [] and .get().
_MAPPINGS = frozenset({"dict", "Dict", "Mapping", "MutableMapping", "Any", "object", "JSON"})
# Annotations of a value that is not the producer's output.
_PRIMITIVES = frozenset({"str", "int", "float", "bool", "bytes", "None"})
# Annotations of a list of values; the producer's output is each item.
_SEQUENCES = frozenset(
    {"list", "List", "Sequence", "Iterable", "Collection", "tuple", "Tuple", "set", "frozenset"}
)
# Annotations that only wrap the type that matters.
_WRAPPERS = frozenset({"Optional", "Annotated", "Required", "NotRequired", "ReadOnly", "Final"})
# Framework results that hold the agent's output in one attribute.
RESULT_WRAPPERS = {"RunResult": "final_output", "RunResultStreaming": "final_output"}
# How deep nested types are followed.
_MAX_DEPTH = 4


class PyModule:
    """One parsed Python file: its classes and the names it imports."""

    def __init__(self, path: Path, tree: ast.Module) -> None:
        self.path = path
        self.classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
        self.imports: dict[str, tuple[str, str, int]] = {}
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    local = alias.asname or alias.name
                    self.imports[local] = (node.module or "", alias.name, node.level)

    def annotation(self, node: ast.expr | None) -> Annotation:
        """Describe a parameter annotation."""
        if node is None:
            return Annotation()
        return self._annotation(_unstring(node), depth=0)

    def _annotation(self, node: ast.expr, depth: int) -> Annotation:
        name = _name(node)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return self._union([node.left, node.right], depth)
        if isinstance(node, ast.Constant) and node.value is None:
            return Annotation(primitive=True, present=True)
        if isinstance(node, ast.Subscript):
            outer = _name(node.value)
            args = _subscript_args(node)
            if outer in _WRAPPERS and args:
                return self._annotation(_unstring(args[0]), depth)
            if outer == "Union":
                return self._union(args, depth)
            if outer in _SEQUENCES and args:
                inner = self._annotation(_unstring(args[0]), depth)
                return Annotation(shape=inner.shape, items=True, present=True)
            if outer in _MAPPINGS:
                return Annotation(mapping=True, present=True)
            name = outer
        if name in RESULT_WRAPPERS:
            return Annotation(present=True, wrapper=RESULT_WRAPPERS[name])
        if name in _MAPPINGS:
            return Annotation(mapping=True, present=True)
        if name in _PRIMITIVES:
            return Annotation(primitive=True, present=True)
        if name in _SEQUENCES:
            return Annotation(items=True, present=True)
        shape = self.shape(name, depth) if name else None
        return Annotation(shape=shape, present=True)

    def _union(self, members: list[ast.expr], depth: int) -> Annotation:
        """``X | None`` is X; several types are known only when they agree."""
        found = [self._annotation(_unstring(m), depth) for m in members]
        useful = [a for a in found if not (a.primitive and not a.mapping)]
        if len(useful) == 1:
            return useful[0]
        wrappers = {a.wrapper for a in useful}
        if len(wrappers) == 1 and None not in wrappers:
            return useful[0]
        return Annotation(present=True, primitive=not useful)

    def shape(self, name: str, depth: int = 0) -> TypeShape | None:
        """The fields of the class ``name`` if it is a model, a TypedDict or a dataclass."""
        if depth > _MAX_DEPTH:
            return None
        if name in self.classes:
            return self._class_shape(self.classes[name], depth)
        if name in self.imports:
            module, original, level = self.imports[name]
            other = _load(_module_file(self.path, module, level))
            if other is not None:
                return other.shape(original, depth + 1)
        return None

    def _class_shape(self, cls: ast.ClassDef, depth: int) -> TypeShape | None:
        kind = self._kind(cls, depth)
        if kind is None:
            return None
        fields: dict[str, FieldShape] = {}
        for base in cls.bases:
            base_name = _name(base)
            base_shape = self.shape(base_name, depth + 1) if base_name else None
            if base_shape is not None:
                fields.update(base_shape.fields)
        total = not any(
            k.arg == "total" and isinstance(k.value, ast.Constant) and k.value.value is False
            for k in cls.keywords
        )
        for stmt in cls.body:
            if not (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)):
                continue
            annotation = _unstring(stmt.annotation)
            if _name(annotation) == "ClassVar" or (
                isinstance(annotation, ast.Subscript) and _name(annotation.value) == "ClassVar"
            ):
                continue
            if kind == "typeddict":
                required = _typeddict_required(annotation, total)
            else:
                required = stmt.value is None
            inner = self._annotation(annotation, depth + 1)
            fields[stmt.target.id] = FieldShape(
                required=required,
                nested=None if inner.items else inner.shape,
                item=inner.shape if inner.items else None,
            )
        return TypeShape(cls.name, fields)

    def _kind(self, cls: ast.ClassDef, depth: int) -> str | None:
        for decorator in cls.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if _name(target) == "dataclass":
                return "dataclass"
        for base in cls.bases:
            base_name = _name(base)
            if base_name == "TypedDict":
                return "typeddict"
            if base_name in ("BaseModel", "RootModel"):
                return "model"
            if base_name and base_name not in _MAPPINGS and self.shape(base_name, depth + 1):
                return "model"
        return None


def _typeddict_required(annotation: ast.expr, total: bool) -> bool:
    if isinstance(annotation, ast.Subscript):
        outer = _name(annotation.value)
        if outer == "NotRequired":
            return False
        if outer == "Required":
            return True
    return total


def _name(node: ast.expr) -> str:
    """The last part of a name: ``Report`` for ``Report`` and ``models.Report``."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _subscript_args(node: ast.Subscript) -> list[ast.expr]:
    return list(node.slice.elts) if isinstance(node.slice, ast.Tuple) else [node.slice]


def _unstring(node: ast.expr) -> ast.expr:
    """A string annotation (``"Report"``) parsed as code."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            return ast.parse(node.value, mode="eval").body
        except SyntaxError:
            return node
    return node


def _module_file(source: Path, module: str, level: int) -> Path | None:
    """The file of ``from <module> import ...`` written in ``source``."""
    parts = module.split(".") if module else []
    if level:
        base = source.parent
        for _ in range(level - 1):
            base = base.parent
        return _existing(base, parts)
    # An absolute import inside the project: try each parent directory.
    for base in source.parents:
        found = _existing(base, parts)
        if found is not None:
            return found
    return None


def _existing(base: Path, parts: list[str]) -> Path | None:
    if not parts:
        init = base / "__init__.py"
        return init if init.is_file() else None
    target = base.joinpath(*parts)
    for candidate in (target.with_suffix(".py"), target / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


_CACHE: dict[tuple[Path, int], PyModule | None] = {}


def _load(path: Path | None) -> PyModule | None:
    """Parse an imported module once per version of the file."""
    if path is None:
        return None
    try:
        key = (path.resolve(), path.stat().st_mtime_ns)
    except OSError:
        return None
    if key not in _CACHE:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            _CACHE[key] = None
        else:
            _CACHE[key] = PyModule(path, tree)
    return _CACHE[key]

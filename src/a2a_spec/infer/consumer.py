"""Static analysis of which input fields a consumer agent reads."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path

from a2a_spec.exceptions import ConfigError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FieldRead:
    """One read of a top-level input field.

    ``strict`` is True for ``data["key"]``, which raises when the key is
    missing, and False for ``data.get("key")`` or ``"key" in data``.
    """

    name: str
    line: int
    strict: bool


@dataclass(frozen=True)
class ConsumerReads:
    """Everything the analyzer learned about one consumer function."""

    source: str
    param: str
    reads: list[FieldRead] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def fields(self) -> list[str]:
        """Field names in first-read order, without duplicates."""
        return list(dict.fromkeys(r.name for r in self.reads))


def parse_source_ref(ref: str) -> tuple[Path, str]:
    """Split ``path/to/file.py:function`` into its parts."""
    path, sep, function = ref.rpartition(":")
    if not sep or not path or not function:
        raise ConfigError(f"Consumer source must look like 'path/to/file.py:function', got '{ref}'")
    return Path(path), function


def analyze_consumer(path: str | Path, function: str) -> ConsumerReads:
    """Find the input fields a consumer function reads.

    The function's first parameter (after ``self``/``cls``) is treated as
    the producer's output. Only top-level string keys are tracked; any
    other use of the parameter is reported as a warning because the
    contract may then be incomplete.

    Raises:
        ConfigError: If the file or function cannot be found or parsed.
    """
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Consumer source not found: {path}")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as e:
        raise ConfigError(f"Cannot parse {path}: {e}") from e

    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == function
    ]
    if not matches:
        raise ConfigError(f"Function '{function}' not found in {path}")
    if len(matches) > 1:
        lines = ", ".join(str(m.lineno) for m in matches)
        raise ConfigError(f"Function '{function}' is defined more than once in {path} ({lines})")
    fn = matches[0]

    params = [a.arg for a in fn.args.posonlyargs + fn.args.args]
    if params and params[0] in ("self", "cls"):
        params = params[1:]
    if not params:
        raise ConfigError(f"Function '{function}' in {path} takes no input parameter")

    visitor = _ReadVisitor(params[0])
    for stmt in fn.body:
        visitor.visit(stmt)
    logger.debug("Consumer %s:%s reads %d field(s)", path, function, len(visitor.reads))
    return ConsumerReads(
        source=f"{path}:{function}",
        param=params[0],
        reads=visitor.reads,
        warnings=visitor.warnings,
    )


class _ReadVisitor(ast.NodeVisitor):
    def __init__(self, param: str) -> None:
        self.param = param
        self.reads: list[FieldRead] = []
        self.warnings: list[str] = []

    def _is_param(self, node: ast.AST) -> bool:
        return isinstance(node, ast.Name) and node.id == self.param

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if self._is_param(node.value) and isinstance(node.ctx, ast.Load):
            key = node.slice
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                self.reads.append(FieldRead(key.value, node.lineno, strict=True))
            else:
                self._warn(node, "reads a non-literal key")
            self.visit(key)
            return
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and self._is_param(func.value):
            if func.attr == "get" and node.args:
                key = node.args[0]
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    self.reads.append(FieldRead(key.value, node.lineno, strict=False))
                else:
                    self._warn(node, "calls .get() with a non-literal key")
            else:
                self._warn(node, f"calls .{func.attr}()")
            for child in [*node.args[1:], *node.keywords]:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        if (
            len(node.ops) == 1
            and isinstance(node.ops[0], ast.In | ast.NotIn)
            and self._is_param(node.comparators[0])
            and isinstance(node.left, ast.Constant)
            and isinstance(node.left.value, str)
        ):
            self.reads.append(FieldRead(node.left.value, node.lineno, strict=False))
            return
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id != self.param:
            return
        if isinstance(node.ctx, ast.Load):
            self._warn(node, "is used as a whole")
        else:
            self._warn(node, "is reassigned")

    def _warn(self, node: ast.expr, what: str) -> None:
        self.warnings.append(
            f"line {node.lineno}: '{self.param}' {what}; the inferred contract may be incomplete"
        )

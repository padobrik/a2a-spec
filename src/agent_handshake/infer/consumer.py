"""Static analysis of which input fields a consumer agent reads."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path

from agent_handshake.exceptions import ConfigError

logger = logging.getLogger(__name__)

# Files read by the TypeScript analyzer (agent_handshake.infer.ts_consumer).
TS_LIKE_SUFFIXES = frozenset({".ts", ".mts", ".cts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"})


@dataclass(frozen=True)
class FieldRead:
    """One read of an input field, possibly nested.

    ``path`` is the chain of keys from the input, for example
    ``("customer", "tier")`` for ``data["customer"]["tier"]``. ``strict`` has
    one flag per key: True for ``x["key"]``, which raises when the key is
    missing, and False for ``x.get("key")`` or ``"key" in x``.
    """

    path: tuple[str, ...]
    line: int
    strict: tuple[bool, ...]

    @property
    def name(self) -> str:
        """The dotted path, for messages: ``customer.tier``."""
        return ".".join(self.path)


@dataclass(frozen=True)
class ConsumerReads:
    """Everything the analyzer learned about one consumer function."""

    source: str
    param: str
    reads: list[FieldRead] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def fields(self) -> list[str]:
        """Dotted paths in first-read order, without duplicates."""
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
    the producer's output. Literal string keys are tracked through nested
    reads (``data["a"]["b"]``, ``data.get("a", {}).get("b")``) and through
    local names bound to a nested value (``a = data["a"]``). Any other use
    of the input is reported as a warning because the contract may then be
    incomplete.

    Raises:
        ConfigError: If the file or function cannot be found or parsed.
    """
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Consumer source not found: {path}")
    if path.suffix in TS_LIKE_SUFFIXES:
        from agent_handshake.infer.ts_consumer import analyze_ts_consumer

        return analyze_ts_consumer(path, function)
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
    visitor.finish()
    logger.debug("Consumer %s:%s reads %d field(s)", path, function, len(visitor.reads))
    return ConsumerReads(
        source=f"{path}:{function}",
        param=params[0],
        reads=visitor.reads,
        warnings=visitor.warnings,
    )


Chain = tuple[tuple[str, ...], tuple[bool, ...]]

_MAPPING_METHODS = frozenset(
    {"get", "items", "keys", "values", "copy", "pop", "setdefault", "update"}
)


class _ReadVisitor(ast.NodeVisitor):
    """Records key chains rooted at the input parameter or at a local alias of it."""

    def __init__(self, param: str) -> None:
        self.param = param
        self.aliases: dict[str, Chain] = {}
        self.reads: list[FieldRead] = []
        self.warnings: list[str] = []
        # An alias may hold a leaf value (``tier = data["tier"]``), so using it
        # as a whole is only worth a warning when the code also reads keys from it.
        self._mapping_aliases: set[str] = set()
        self._whole_alias_uses: list[tuple[str, Chain, int]] = []

    def finish(self) -> None:
        """Report whole uses of aliases that the code also reads keys from."""
        for name, chain, line in self._whole_alias_uses:
            if name in self._mapping_aliases:
                self.warnings.append(
                    f"line {line}: {self._label(chain)} is used as a whole; "
                    "the inferred contract may be incomplete"
                )

    # -- resolving expressions to key chains ---------------------------------

    def _chain(self, node: ast.AST) -> Chain | None:
        """The key chain an expression reads, or None if it is not rooted in the input."""
        if isinstance(node, ast.Name):
            if node.id == self.param:
                return (), ()
            return self.aliases.get(node.id)
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
            base = self._base(node.value)
            key = node.slice
            if base is not None and isinstance(key, ast.Constant) and isinstance(key.value, str):
                return base[0] + (key.value,), base[1] + (True,)
            return None
        if self._is_get(node):
            assert isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            base = self._base(node.func.value)
            key = node.args[0]
            if base is not None and isinstance(key, ast.Constant) and isinstance(key.value, str):
                return base[0] + (key.value,), base[1] + (False,)
        return None

    def _base(self, node: ast.AST) -> Chain | None:
        """Resolve an expression that keys are read from, noting aliases used as mappings."""
        if isinstance(node, ast.Name) and node.id in self.aliases:
            self._mapping_aliases.add(node.id)
        return self._chain(node)

    @staticmethod
    def _is_get(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and bool(node.args)
        )

    def _record(self, chain: Chain, line: int) -> None:
        if chain[0]:
            self.reads.append(FieldRead(chain[0], line, chain[1]))

    def _record_use(self, node: ast.AST, chain: Chain, line: int) -> None:
        """Record a use of ``node``; a local alias was recorded when it was bound."""
        if not (isinstance(node, ast.Name) and node.id in self.aliases):
            self._record(chain, line)

    def _label(self, chain: Chain) -> str:
        return f"'{self.param}'" if not chain[0] else f"'{'.'.join(chain[0])}'"

    # -- visiting --------------------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        chain = self._chain(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                if target.id == self.param:
                    self._warn(target, "is reassigned")
                elif chain is not None and chain[0]:
                    self.aliases[target.id] = chain
                else:
                    self.aliases.pop(target.id, None)
            else:
                self.visit(target)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if isinstance(node.ctx, ast.Load):
            chain = self._chain(node)
            if chain is not None:
                self._record(chain, node.lineno)
                return
            base = self._base(node.value)
            if base is not None:  # rooted in the input, but the key is not a literal
                key = node.slice
                is_index = isinstance(key, ast.Constant) and isinstance(key.value, int)
                if not (base[0] and is_index):  # a nested list index tells nothing new
                    self._warn(node, "reads a non-literal key", base)
                self._record_use(node.value, base, node.lineno)
                self.visit(node.slice)
                return
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        chain = self._chain(node)
        if chain is not None:
            self._record(chain, node.lineno)
            for child in [*node.args[1:], *node.keywords]:
                self.visit(child)
            return
        func = node.func
        if isinstance(func, ast.Attribute):
            base = self._chain(func.value)
            if base is not None:
                # A method on a nested value is often a string or list method
                # (``data["tier"].lower()``); only mapping methods hide reads there.
                if not base[0] or func.attr in _MAPPING_METHODS:
                    if func.attr == "get":
                        what = "calls .get() with a non-literal key"
                    else:
                        what = f"calls .{func.attr}()"
                    self._warn(node, what, base)
                self._record_use(func.value, base, node.lineno)
                for child in [*node.args, *node.keywords]:
                    self.visit(child)
                return
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        if (
            len(node.ops) == 1
            and isinstance(node.ops[0], ast.In | ast.NotIn)
            and isinstance(node.left, ast.Constant)
            and isinstance(node.left.value, str)
        ):
            base = self._base(node.comparators[0])
            if base is not None:
                self._record((base[0] + (node.left.value,), base[1] + (False,)), node.lineno)
                return
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        chain = self._chain(node)
        if chain is None:
            return
        if node.id != self.param:
            if isinstance(node.ctx, ast.Load):
                self._whole_alias_uses.append((node.id, chain, node.lineno))
        elif isinstance(node.ctx, ast.Load):
            self._warn(node, "is used as a whole", chain)
        else:
            self._warn(node, "is reassigned")

    def _warn(self, node: ast.AST, what: str, chain: Chain | None = None) -> None:
        label = self._label(chain) if chain else f"'{self.param}'"
        line = getattr(node, "lineno", 0)
        self.warnings.append(
            f"line {line}: {label} {what}; the inferred contract may be incomplete"
        )

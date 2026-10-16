"""Static analysis of which input fields a consumer agent reads."""

from __future__ import annotations

import ast
import logging
from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path

from agent_handshake.exceptions import ConfigError
from agent_handshake.infer.py_types import PyModule
from agent_handshake.infer.shapes import Annotation, choose_param, no_matching_param, undeclared

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


def analyze_consumer(
    path: str | Path, function: str, keys: Collection[str] | None = None
) -> ConsumerReads:
    """Find the input fields a consumer function reads.

    The parameter that holds the producer's output is chosen by its
    annotation: a Pydantic model, TypedDict or dataclass, and with several
    such parameters the one whose fields share the most names with ``keys``
    (the producer's output keys). Without one, the first parameter (after
    ``self``/``cls``) that is not a plain ``str``, ``int`` and the like.

    Literal string keys are tracked through nested reads (``data["a"]["b"]``,
    ``data.get("a", {}).get("b")``) and through local names bound to a nested
    value (``a = data["a"]``). On an annotated object, attribute reads
    (``report.summary``, ``getattr(report, "summary", "")``) are tracked too.
    Any other use of the input is reported as a warning because the contract
    may then be incomplete.

    Raises:
        ConfigError: If the file or function cannot be found or parsed.
    """
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Consumer source not found: {path}")
    if path.suffix in TS_LIKE_SUFFIXES:
        from agent_handshake.infer.ts_consumer import analyze_ts_consumer

        return analyze_ts_consumer(path, function, keys)
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

    args = [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]
    if args and args[0].arg in ("self", "cls"):
        args = args[1:]
    if not args:
        raise ConfigError(f"Function '{function}' in {path} takes no input parameter")

    module = PyModule(path, tree)

    def visit(param: str, annotation: Annotation) -> _ReadVisitor:
        visitor = _ReadVisitor(param, annotation)
        for stmt in fn.body:
            visitor.visit(stmt)
        visitor.finish()
        return visitor

    described = [(a.arg, module.annotation(a.annotation)) for a in args]
    chosen = choose_param(described, keys, lambda p, a: {r.path[0] for r in visit(p, a).reads})
    if chosen is None:
        raise ConfigError(no_matching_param(function, path, [p for p, _ in described], keys))
    param, annotation = chosen
    visitor = visit(param, annotation)
    logger.debug("Consumer %s:%s reads %d field(s)", path, function, len(visitor.reads))
    return ConsumerReads(
        # POSIX separators, so a spec inferred on Windows checks on Linux and back.
        source=f"{path.as_posix()}:{function}",
        param=param,
        reads=visitor.reads,
        warnings=visitor.warnings,
    )


Chain = tuple[tuple[str, ...], tuple[bool, ...]]

_MAPPING_METHODS = frozenset(
    {"get", "items", "keys", "values", "copy", "pop", "setdefault", "update"}
)


class _ReadVisitor(ast.NodeVisitor):
    """Records key chains rooted at the input parameter or at a local alias of it."""

    def __init__(self, param: str, annotation: Annotation | None = None) -> None:
        self.param = param
        annotation = annotation or Annotation()
        # An annotated parameter that is not a dict is an object: its
        # attributes are its fields. A list parameter holds one output per item.
        self.object_mode = annotation.present and not annotation.mapping
        self.items = annotation.items
        self.wrapper = annotation.wrapper
        self.shape = annotation.shape
        self.aliases: dict[str, Chain] = {}
        self.reads: list[FieldRead] = []
        self.warnings: list[str] = []
        # An alias may hold a leaf value (``tier = data["tier"]``), so using it
        # as a whole is only worth a warning when the code also reads keys from it.
        self._mapping_aliases: set[str] = set()
        self._whole_alias_uses: list[tuple[str, Chain, int]] = []
        # Names that hold a part of the input the analysis does not follow:
        # ``x = data.get("k") or {}`` or a list item (``for r in data["rs"]``).
        # Reading keys from them, or passing them on, gets a warning.
        self._untracked: dict[str, str] = {}

    def finish(self) -> None:
        """Report whole uses of aliases that the code also reads keys from."""
        for name, chain, line in self._whole_alias_uses:
            if name in self._mapping_aliases:
                self.warnings.append(
                    f"line {line}: {self._label(chain)} is used as a whole; "
                    "the inferred contract may be incomplete"
                )
        self.warnings += undeclared(self.reads, self.shape)

    # -- resolving expressions to key chains ---------------------------------

    def _chain(self, node: ast.AST) -> Chain | None:
        """The key chain an expression reads, or None if it is not rooted in the input."""
        if isinstance(node, ast.Name):
            if node.id == self.param:
                # A list of outputs or a framework result is not the output itself.
                return None if self.items or self.wrapper else ((), ())
            return self.aliases.get(node.id)
        if self._is_param(node, self.items) and _is_index(node):
            return (), ()  # an item of a list of outputs
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            if self.wrapper and node.attr == self.wrapper and self._is_param(node.value):
                return (), ()
            if self.object_mode:
                base = self._base(node.value)
                if base is not None:
                    return base[0] + (node.attr,), base[1] + (True,)
            return None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and self.wrapper:
            if node.func.attr == f"{self.wrapper}_as" and self._is_param(node.func.value):
                return (), ()  # result.final_output_as(Model)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) in (2, 3)
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            base = self._base(node.args[0])
            if base is not None:
                # getattr without a default raises like an attribute read.
                return base[0] + (node.args[1].value,), base[1] + (len(node.args) == 2,)
            return None
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
            base = self._base(node.value)
            key = node.slice
            if base is not None and isinstance(key, ast.Constant) and isinstance(key.value, str):
                return base[0] + (key.value,), base[1] + (True,)
            return None
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and self._is_get(node)
        ):
            base = self._base(node.func.value)
            key = node.args[0]
            if base is not None and isinstance(key, ast.Constant) and isinstance(key.value, str):
                return base[0] + (key.value,), base[1] + (False,)
        return None

    def _is_param(self, node: ast.AST, subscript: bool = False) -> bool:
        """``node`` is the parameter itself (or, with ``subscript``, an index into it)."""
        if subscript:
            return isinstance(node, ast.Subscript) and self._is_param(node.value)
        return isinstance(node, ast.Name) and node.id == self.param

    def _base(self, node: ast.AST) -> Chain | None:
        """Resolve an expression that keys are read from, noting aliases used as mappings."""
        if isinstance(node, ast.Name) and node.id in self.aliases:
            self._mapping_aliases.add(node.id)
        self._check_untracked(node)
        return self._chain(node)

    def _check_untracked(self, node: ast.AST) -> None:
        """Warn once when a name holding an unfollowed part of the input is read from."""
        if isinstance(node, ast.Name) and node.id in self._untracked:
            what = f"'{node.id}' {self._untracked.pop(node.id)}"
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, int)
            and (chain := self._chain(node.value)) is not None
            and chain[0]
        ):
            what = f"an item of '{'.'.join(chain[0])}' is read"
        else:
            return
        warning = (
            f"line {getattr(node, 'lineno', 0)}: {what}, and its keys are not followed; "
            "the inferred contract may be incomplete"
        )
        if warning not in self.warnings:
            self.warnings.append(warning)

    def _held(self, node: ast.AST) -> tuple[Chain, str] | None:
        """The input part an expression passes on without being a plain read of it."""
        if isinstance(node, ast.BoolOp):
            operator = "or" if isinstance(node.op, ast.Or) else "and"
            for value in node.values:
                chain = self._chain(value)
                if chain is not None and chain[0]:
                    return chain, f"`{operator}`"
        if isinstance(node, ast.IfExp):
            for value in (node.body, node.orelse):
                chain = self._chain(value)
                if chain is not None and chain[0]:
                    return chain, "a conditional expression"
        return None

    def _bind_items(self, target: ast.AST, iterable: ast.AST) -> None:
        """Note a loop or comprehension name that takes the items of an input list."""
        if not isinstance(target, ast.Name):
            return
        if self.items and self._is_param(iterable):
            self.aliases[target.id] = ((), ())  # each item is one output
            self._untracked.pop(target.id, None)
            return
        chain = self._chain(iterable)
        self.aliases.pop(target.id, None)
        if chain is not None and chain[0]:
            self._untracked[target.id] = f"is an item of '{'.'.join(chain[0])}'"
        else:
            self._untracked.pop(target.id, None)

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
                self._untracked.pop(target.id, None)
                held = self._held(node.value) if chain is None else None
                if target.id == self.param:
                    self._warn(target, "is reassigned")
                elif chain is not None and chain[0]:
                    self.aliases[target.id] = chain
                else:
                    self.aliases.pop(target.id, None)
                    if held is not None:
                        label = ".".join(held[0][0])
                        self._untracked[target.id] = f"holds '{label}' through {held[1]}"
            else:
                self.visit(target)

    def visit_For(self, node: ast.For | ast.AsyncFor) -> None:
        self.visit(node.iter)
        self._bind_items(node.target, node.iter)
        for stmt in [*node.body, *node.orelse]:
            self.visit(stmt)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.visit_For(node)

    def _visit_comprehension(
        self, node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp
    ) -> None:
        # Comprehension names are local to the comprehension.
        names = [g.target.id for g in node.generators if isinstance(g.target, ast.Name)]
        saved = {n: (self.aliases.get(n), self._untracked.get(n)) for n in names}
        try:
            self._visit_generators(node)
        finally:
            for name, (alias, untracked) in saved.items():
                self.aliases.pop(name, None)
                self._untracked.pop(name, None)
                if alias is not None:
                    self.aliases[name] = alias
                if untracked is not None:
                    self._untracked[name] = untracked

    def _visit_generators(
        self, node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp
    ) -> None:
        for generator in node.generators:
            self.visit(generator.iter)
            self._bind_items(generator.target, generator.iter)
            for condition in generator.ifs:
                self.visit(condition)
        if isinstance(node, ast.DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            self.visit(node.elt)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load):
            chain = self._chain(node)
            if chain is not None:
                self._record_use(node, chain, node.lineno)
                return
            self._check_untracked(node.value)
            if not self.object_mode and self._chain(node.value) == ((), ()):
                # The input is an object here (a dataclass, a model), not a dict.
                self._warn(node, f"reads the attribute .{node.attr}, which is not followed yet")
                return
        self.generic_visit(node)

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
        for arg in [*node.args, *(k.value for k in node.keywords)]:
            self._check_untracked(arg)
        chain = self._chain(node)
        if chain is not None:
            self._record(chain, node.lineno)
            for child in [*node.args[1:], *node.keywords]:
                self.visit(child)
            return
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if func.value.id in self._untracked:
                # A method of a list item: only mapping methods read its keys.
                if func.attr in _MAPPING_METHODS:
                    self._check_untracked(func.value)
                for child in [*node.args, *node.keywords]:
                    self.visit(child)
                return
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


def _is_index(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, int)
    )

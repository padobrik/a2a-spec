"""Static analysis of which input fields a consumer agent reads."""

from __future__ import annotations

import ast
import logging
from collections.abc import Collection
from dataclasses import dataclass, field, replace
from pathlib import Path

from agent_handshake.exceptions import ConfigError
from agent_handshake.infer.paths import dotted
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
        return dotted(self.path)


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
    scope = _Scope(module, _helpers(tree, fn), local=_bound_names(fn))

    def visit(param: str, annotation: Annotation) -> _ReadVisitor:
        visitor = _ReadVisitor(param, annotation, scope)
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
Function = ast.FunctionDef | ast.AsyncFunctionDef

# How many levels of helper functions are followed.
_MAX_HELPER_DEPTH = 3


@dataclass(frozen=True)
class _Scope:
    """Where helper functions are looked up: the file's functions and the consumer's class."""

    module: PyModule
    helpers: dict[str, tuple[Function, bool]]  # name -> (function, is a method)
    depth: int = 0
    active: frozenset[str] = frozenset()
    # Names the visited function binds itself; a call to one is not a file-level helper.
    local: frozenset[str] = frozenset()


def _bound_names(fn: Function) -> frozenset[str]:
    """Parameters, assigned names and nested definitions of ``fn``."""
    names = {a.arg for a in ast.walk(fn.args) if isinstance(a, ast.arg)}
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif node is not fn and isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.Import | ast.ImportFrom):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
    return frozenset(names)


def _helpers(tree: ast.Module, fn: Function) -> dict[str, tuple[Function, bool]]:
    """Top-level functions of the file, and the methods of the class that holds ``fn``."""
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]
    found: dict[str, tuple[Function, bool]] = {n.name: (n, False) for n in functions}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and fn in node.body:
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    found[f"self.{item.name}"] = (item, True)
    return found


_MAPPING_METHODS = frozenset(
    {"get", "items", "keys", "values", "copy", "pop", "setdefault", "update"}
)


class _ReadVisitor(ast.NodeVisitor):
    """Records key chains rooted at the input parameter or at a local alias of it."""

    def __init__(
        self,
        param: str,
        annotation: Annotation | None = None,
        scope: _Scope | None = None,
        root: Chain = ((), ()),
    ) -> None:
        self.param = param
        # In a helper function, the parameter holds the part of the input at ``root``.
        self.root = root
        self.scope = scope
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
        self._mapping_aliases: set[tuple[str, Chain]] = set()
        self._whole_alias_uses: list[tuple[str, Chain, int]] = []
        self._branches = 0  # how deep the visit is inside if blocks

    def finish(self, check_shape: bool = True) -> None:
        """Report whole uses of aliases that the code also reads keys from."""
        for name, chain, line in self._whole_alias_uses:
            if (name, chain) in self._mapping_aliases:
                self._add_warning(
                    f"line {line}: {self._label(chain)} is used as a whole; "
                    "the inferred contract may be incomplete"
                )
        if check_shape:
            self.warnings += undeclared(self.reads, self.shape)

    def _add_warning(self, warning: str) -> None:
        if warning not in self.warnings:
            self.warnings.append(warning)

    # -- resolving expressions to key chains ---------------------------------

    def _chain(self, node: ast.AST) -> Chain | None:
        """The key chain an expression reads, or None if it is not rooted in the input."""
        if isinstance(node, ast.Name):
            if node.id == self.param:
                # A list of outputs or a framework result is not the output itself.
                return None if self.items or self.wrapper else self.root
            return self.aliases.get(node.id)
        if self.items and self._is_param(node, True) and _is_index(node):
            return self.root  # an item of a list of outputs
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            if self.wrapper and node.attr == self.wrapper and self._is_param(node.value):
                return self.root
            if self.object_mode:
                base = self._base(node.value)
                if base is not None:
                    return base[0] + (node.attr,), base[1] + (True,)
            return None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and self.wrapper:
            if node.func.attr == f"{self.wrapper}_as" and self._is_param(node.func.value):
                return self.root  # result.final_output_as(Model)
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
            if base is not None and base[0] and _is_index(node):
                return base[0] + ("[]",), base[1] + (True,)  # an item of an input list
            if base is not None and base[0] and isinstance(key, ast.Slice):
                return base  # a slice of an input list holds the same items
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
            self._mapping_aliases.add((node.id, self.aliases[node.id]))
        return self._chain(node)

    def _held(self, node: ast.AST) -> Chain | None:
        """The input part ``x or {}`` or ``x if c else {}`` passes on; it may be missing."""
        values: list[ast.expr] = []
        if isinstance(node, ast.BoolOp):
            values = list(node.values)
        elif isinstance(node, ast.IfExp):
            values = [node.body, node.orelse]
        for value in values:
            chain = self._chain(value)
            if chain is not None and chain[0]:
                return chain[0], (*chain[1][:-1], False)
        return None

    def _bind_items(self, target: ast.AST, iterable: ast.AST) -> None:
        """Bind a loop or comprehension name to the items of an input list."""
        if not isinstance(target, ast.Name):
            return
        if self.items and self._is_param(iterable):
            self.aliases[target.id] = self.root  # each item is one output
            return
        chain = self._chain(iterable) or self._held(iterable)  # also `for x in (xs or [])`
        if chain is not None and chain[0]:
            self.aliases[target.id] = ((*chain[0], "[]"), (*chain[1], False))
        else:
            self.aliases.pop(target.id, None)

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
        return f"'{self.param}'" if not chain[0] else f"'{dotted(chain[0])}'"

    # -- visiting --------------------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        chain = self._chain(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                held = self._held(node.value) if chain is None else chain
                if target.id == self.param:
                    self._warn(target, "is reassigned")
                elif held is not None and held[0]:
                    self.aliases[target.id] = held
                elif not (self._branches and target.id in self.aliases and _empty(node.value)):
                    # `if not isinstance(h, dict): h = {}` is a fallback: h still
                    # refers to the input part. Outside a branch, `h = {}` replaces it.
                    self.aliases.pop(target.id, None)
            else:
                self.visit(target)

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        self._branches += 1
        try:
            for stmt in [*node.body, *node.orelse]:
                self.visit(stmt)
        finally:
            self._branches -= 1

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
        saved = {n: self.aliases.get(n) for n in names}
        try:
            self._visit_generators(node)
        finally:
            for name, alias in saved.items():
                self.aliases.pop(name, None)
                if alias is not None:
                    self.aliases[name] = alias

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
            base = self._chain(node.value)
            if not self.object_mode and base is not None and (base == self.root or _item(base)):
                # The input (or a list item) is an object here, not a dict.
                what = f"reads the attribute .{node.attr}, which is not followed yet"
                self._warn(node, what, None if base == self.root else base)
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
        followed = self._follow(node)
        if followed is not None:
            for arg in [*node.args, *(k.value for k in node.keywords)]:
                if id(arg) not in followed:
                    self.visit(arg)
            return
        for arg in [*node.args, *(k.value for k in node.keywords)]:
            item = self._chain(arg) if isinstance(arg, ast.Name) else None
            if isinstance(arg, ast.Name) and item is not None and _item(item):
                # A list item given to a function that is not followed.
                self._add_warning(
                    f"line {arg.lineno}: '{arg.id}' is an item of '{dotted(item[0][:-1])}' "
                    "and goes to a function that is not followed; "
                    "the inferred contract may be incomplete"
                )
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

    def _follow(self, node: ast.Call) -> set[int] | None:
        """Read a helper in the same file that gets a part of the input.

        Returns the ids of the arguments whose reads were followed, or None
        when the call is not to such a helper.
        """
        scope = self.scope
        if scope is None or scope.depth >= _MAX_HELPER_DEPTH:
            return None
        func = node.func
        if isinstance(func, ast.Name):
            if func.id in scope.local:
                return None  # a parameter or local name, not the file's function
            name = func.id
        elif (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id in ("self", "cls")
        ):
            name = f"self.{func.attr}"
        else:
            return None
        if name not in scope.helpers or name in scope.active:
            return None
        helper, is_method = scope.helpers[name]
        params = [*helper.args.posonlyargs, *helper.args.args]
        if is_method and params and params[0].arg in ("self", "cls"):
            params = params[1:]
        by_name = {a.arg: a for a in [*params, *helper.args.kwonlyargs]}
        pairs: list[tuple[ast.expr, ast.arg | None]] = [
            (arg, param) for arg, param in zip(node.args, params, strict=False)
        ]
        pairs += [(k.value, by_name.get(k.arg or "")) for k in node.keywords]
        inner = replace(
            scope,
            depth=scope.depth + 1,
            active=scope.active | {name},
            local=_bound_names(helper),
        )
        followed: set[int] = set()
        for arg, param in pairs:
            chain = self._chain(arg) if param is not None else None
            if chain is None or param is None or isinstance(arg, ast.Starred):
                continue
            annotation = scope.module.annotation(param.annotation)
            if not annotation.present:
                # An unannotated helper parameter is read like the value given to it.
                annotation = Annotation(present=self.object_mode)
            child = _ReadVisitor(param.arg, annotation, inner, root=chain)
            for stmt in helper.body:
                child.visit(stmt)
            child.finish(check_shape=False)
            self._record_use(arg, chain, arg.lineno)
            self.reads += child.reads
            for warning in child.warnings:
                self._add_warning(warning)
            followed.add(id(arg))
        return followed if followed else None

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


def _item(chain: Chain) -> bool:
    """The chain is an item of an input list (``rs[]``)."""
    return bool(chain[0]) and chain[0][-1] == "[]"


def _empty(node: ast.AST) -> bool:
    """An empty literal container, such as ``{}``, ``[]`` or ``dict()``."""
    if isinstance(node, ast.Dict | ast.List | ast.Tuple | ast.Set):
        return not (node.keys if isinstance(node, ast.Dict) else node.elts)
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("dict", "list", "tuple", "set")
        and not node.args
        and not node.keywords
    )

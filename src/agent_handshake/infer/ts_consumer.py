"""Static analysis of which input fields a TypeScript or JavaScript consumer reads.

Needs the ``typescript`` extra (tree-sitter with the TypeScript grammar). The
result has the same shape as for Python consumers, so the spec builder and
``handshake infer --check`` work unchanged.

Strictness follows what fails at run time. Reading a missing key in
JavaScript gives ``undefined`` and never throws, so the last key of a read is
always optional. A key is strict when the code goes on to use it without a
fallback: ``data.customer.tier`` throws when ``customer`` is missing, while
``data.customer?.tier`` and ``const { customer = {} } = data`` do not.
"""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import TYPE_CHECKING

from agent_handshake.exceptions import ConfigError
from agent_handshake.infer.consumer import ConsumerReads
from agent_handshake.infer.shapes import Annotation, choose_param, no_matching_param
from agent_handshake.infer.ts_reads import ReadVisitor, TsScope
from agent_handshake.infer.ts_syntax import first_error, node_line, node_text, parameters
from agent_handshake.infer.ts_types import TsModule

if TYPE_CHECKING:
    from tree_sitter import Node

# The TSX grammar also parses plain JavaScript, with or without JSX; the
# other suffixes in TS_LIKE_SUFFIXES (.ts, .mts, .cts) use the TypeScript one.
TSX_SUFFIXES = frozenset({".tsx", ".js", ".jsx", ".mjs", ".cjs"})
_FUNCTIONS = frozenset({"arrow_function", "function_expression", "function"})


def analyze_ts_consumer(
    path: Path, function: str, keys: Collection[str] | None = None
) -> ConsumerReads:
    """Find the input fields a TypeScript or JavaScript function reads.

    The parameter that holds the producer's output is chosen by its type, as
    for Python consumers (see ``analyze_consumer``).

    Raises:
        ConfigError: If the extra is missing, or the file or function cannot be
            parsed or found.
    """
    try:
        import tree_sitter
        import tree_sitter_typescript
    except ImportError as e:
        raise ConfigError(
            "Reading TypeScript or JavaScript consumers needs the 'typescript' extra: "
            'pip install "agent-handshake[typescript]"'
        ) from e

    grammar = (
        tree_sitter_typescript.language_tsx()
        if path.suffix in TSX_SUFFIXES
        else tree_sitter_typescript.language_typescript()
    )
    parser = tree_sitter.Parser(tree_sitter.Language(grammar))
    tree = parser.parse(path.read_bytes())
    error = first_error(tree.root_node)
    if error is not None:
        raise ConfigError(f"Cannot parse {path}: syntax error at line {node_line(error)}")

    matches = [node for name, node in _functions(tree.root_node) if name == function]
    if not matches:
        raise ConfigError(f"Function '{function}' not found in {path}")
    if len(matches) > 1:
        lines = ", ".join(str(node_line(m)) for m in matches)
        raise ConfigError(f"Function '{function}' is defined more than once in {path} ({lines})")
    fn = matches[0]

    params = parameters(fn)
    if not params:
        raise ConfigError(f"Function '{function}' in {path} takes no input parameter")
    module = TsModule(path, tree.root_node, parser)
    body = fn.child_by_field_name("body")
    named: dict[str, list[Node]] = {}
    for name, node in _functions(tree.root_node):
        named.setdefault(name, []).append(node)
    scope = TsScope(module, {n: nodes[0] for n, nodes in named.items() if len(nodes) == 1})

    def visit(pattern: Node, annotation: Annotation) -> ReadVisitor:
        if pattern.type == "identifier":
            visitor = ReadVisitor(node_text(pattern), annotation, scope)
        else:
            visitor = ReadVisitor(None, scope=scope)
            visitor.destructure(pattern, ((), ()))
        if body is not None:
            visitor.visit(body)
        visitor.finish()
        return visitor

    described = [(p, module.annotation(t)) for p, t in params]
    chosen = choose_param(described, keys, lambda p, a: {r.path[0] for r in visit(p, a).reads})
    if chosen is None:
        names = [node_text(p) for p, _ in described]
        raise ConfigError(no_matching_param(function, path, names, keys))
    pattern, annotation = chosen
    visitor = visit(pattern, annotation)
    return ConsumerReads(
        # POSIX separators, so a spec inferred on Windows checks on Linux and back.
        source=f"{path.as_posix()}:{function}",
        param=visitor.param or node_text(pattern),
        reads=visitor.reads,
        warnings=visitor.warnings,
    )


def _functions(root: Node) -> list[tuple[str, Node]]:
    """Every named function: declarations, methods, and functions bound to a name."""
    found: list[tuple[str, Node]] = []
    stack = [root]
    while stack:
        node = stack.pop()
        name: Node | None = None
        target: Node | None = None
        if node.type in (
            "function_declaration",
            "generator_function_declaration",
            "method_definition",
        ):
            name, target = node.child_by_field_name("name"), node
        elif node.type in ("variable_declarator", "pair"):
            value = node.child_by_field_name("value")
            if value is not None and value.type in _FUNCTIONS:
                key = "name" if node.type == "variable_declarator" else "key"
                name, target = node.child_by_field_name(key), value
        if name is not None and target is not None:
            found.append((node_text(name), target))
        stack.extend(reversed(node.named_children))
    return sorted(found, key=lambda item: item[1].start_byte)

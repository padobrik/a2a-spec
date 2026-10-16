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

from pathlib import Path
from typing import TYPE_CHECKING

from agent_handshake.exceptions import ConfigError
from agent_handshake.infer.consumer import ConsumerReads
from agent_handshake.infer.ts_reads import ReadVisitor
from agent_handshake.infer.ts_syntax import first_error, node_line, node_text

if TYPE_CHECKING:
    from tree_sitter import Node

# The TSX grammar also parses plain JavaScript, with or without JSX; the
# other suffixes in TS_LIKE_SUFFIXES (.ts, .mts, .cts) use the TypeScript one.
TSX_SUFFIXES = frozenset({".tsx", ".js", ".jsx", ".mjs", ".cjs"})
_FUNCTIONS = frozenset({"arrow_function", "function_expression", "function"})


def analyze_ts_consumer(path: Path, function: str) -> ConsumerReads:
    """Find the input fields a TypeScript or JavaScript function reads.

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

    pattern = _first_parameter(fn)
    if pattern is None:
        raise ConfigError(f"Function '{function}' in {path} takes no input parameter")

    if pattern.type == "identifier":
        visitor = ReadVisitor(node_text(pattern))
    else:
        visitor = ReadVisitor(None)
        visitor.destructure(pattern, ((), ()))
    body = fn.child_by_field_name("body")
    if body is not None:
        visitor.visit(body)
    visitor.finish()
    return ConsumerReads(
        source=f"{path}:{function}",
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


def _first_parameter(fn: Node) -> Node | None:
    """The pattern of the first parameter, skipping a TypeScript ``this`` parameter."""
    single = fn.child_by_field_name("parameter")  # x => ...
    if single is not None:
        return single
    params = fn.child_by_field_name("parameters")
    for param in params.named_children if params is not None else []:
        pattern = param.child_by_field_name("pattern") if "parameter" in param.type else param
        if pattern is not None and not (pattern.type == "this" or node_text(pattern) == "this"):
            return pattern
    return None

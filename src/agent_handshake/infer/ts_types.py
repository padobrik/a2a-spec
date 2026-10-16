"""What a TypeScript parameter type says about the producer's output.

Finds the declaration of a parameter's type: an ``interface``, a
``type X = { ... }`` literal, or a Zod schema (``const X = z.object({...})``
with ``type X = z.infer<typeof X>``), in the same file or in a file it imports
with a relative path. The code is parsed, never run.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from agent_handshake.infer.shapes import Annotation, FieldShape, TypeShape
from agent_handshake.infer.ts_syntax import node_text, string_value

if TYPE_CHECKING:
    from tree_sitter import Node, Parser

_PRIMITIVES = frozenset(
    {"string", "number", "boolean", "bigint", "symbol", "null", "undefined", "void", "never"}
)
_MAPPINGS = frozenset({"any", "unknown", "object", "Record", "Map", "Object"})
_SEQUENCES = frozenset({"Array", "ReadonlyArray", "Set", "Iterable"})
# Framework results that hold the agent's output in one property.
RESULT_WRAPPERS = {"RunResult": "finalOutput", "StreamedRunResult": "finalOutput"}
# Zod calls that make a property optional.
_ZOD_OPTIONAL = frozenset({"optional", "nullish", "default", "catch"})
_SUFFIXES = (".ts", ".tsx", ".mts", ".cts", ".d.ts", ".js", ".jsx", ".mjs", ".cjs")
_MAX_DEPTH = 4


class TsModule:
    """One parsed file: its type declarations, Zod schemas and imports."""

    def __init__(self, path: Path, root: Node, parser: Parser) -> None:
        self.path = path
        self.parser = parser
        self.types: dict[str, Node] = {}  # interface body, object type or z.infer target
        self.schemas: dict[str, Node] = {}  # const X = z....
        self.imports: dict[str, tuple[str, str]] = {}
        for node in _declarations(root):
            self._collect(node)

    def _collect(self, node: Node) -> None:
        if node.type == "interface_declaration":
            name, body = node.child_by_field_name("name"), node.child_by_field_name("body")
            if name is not None and body is not None:
                self.types[node_text(name)] = body
        elif node.type == "type_alias_declaration":
            name, value = node.child_by_field_name("name"), node.child_by_field_name("value")
            if name is not None and value is not None:
                self.types[node_text(name)] = value
        elif node.type == "lexical_declaration":
            for declarator in node.named_children:
                name = declarator.child_by_field_name("name")
                value = declarator.child_by_field_name("value")
                if name is not None and value is not None and _zod_base(value) is not None:
                    self.schemas[node_text(name)] = value
        elif node.type == "import_statement":
            source = node.child_by_field_name("source")
            spec = string_value(source) if source is not None else None
            if spec is None or not spec.startswith("."):
                return
            for item in _walk(node):
                if item.type == "import_specifier":
                    original = item.child_by_field_name("name")
                    alias = item.child_by_field_name("alias") or original
                    if original is not None and alias is not None:
                        self.imports[node_text(alias)] = (spec, node_text(original))

    def annotation(self, type_node: Node | None) -> Annotation:
        """Describe the type of a parameter (the node inside its ``type_annotation``)."""
        if type_node is None:
            return Annotation()
        return self._annotation(type_node, 0)

    def _annotation(self, node: Node, depth: int) -> Annotation:
        if node.type == "type_annotation" and node.named_children:
            return self._annotation(node.named_children[0], depth)
        if node.type in ("predefined_type", "literal_type"):
            text = node_text(node)
            mapping, primitive = text in _MAPPINGS, text in _PRIMITIVES
            return Annotation(present=True, mapping=mapping, primitive=primitive)
        if node.type == "array_type" and node.named_children:
            inner = self._annotation(node.named_children[0], depth)
            return Annotation(shape=inner.shape, items=True, present=True)
        if node.type == "union_type":
            members = [self._annotation(m, depth) for m in node.named_children]
            useful = [m for m in members if not m.primitive]
            return useful[0] if len(useful) == 1 else Annotation(present=True)
        if node.type == "object_type":
            return Annotation(shape=self._object_shape("(object)", node, depth), present=True)
        name, args = _type_name(node)
        if name in RESULT_WRAPPERS:
            return Annotation(present=True, wrapper=RESULT_WRAPPERS[name])
        if name in _SEQUENCES and args:
            inner = self._annotation(args[0], depth)
            return Annotation(shape=inner.shape, items=True, present=True)
        if name in _MAPPINGS:
            return Annotation(present=True, mapping=True)
        shape = self.shape(name, depth) if name else None
        return Annotation(shape=shape, present=True)

    def shape(self, name: str, depth: int = 0) -> TypeShape | None:
        """The fields of the type or schema called ``name``."""
        if depth > _MAX_DEPTH:
            return None
        if name in self.types:
            return self._type_shape(name, self.types[name], depth)
        if name in self.schemas:
            return self._zod_shape(name, self.schemas[name], depth)
        if name in self.imports:
            spec, original = self.imports[name]
            other = _load(_resolve(self.path, spec), self.parser)
            if other is not None:
                return other.shape(original, depth + 1)
        return None

    def _type_shape(self, name: str, node: Node, depth: int) -> TypeShape | None:
        if node.type in ("interface_body", "object_type"):
            return self._object_shape(name, node, depth)
        type_name, args = _type_name(node)
        if type_name == "infer" and args and args[0].type == "type_query":
            target = args[0].named_children
            if target:
                return self.shape(node_text(target[0]), depth + 1)
        return None

    def _object_shape(self, name: str, body: Node, depth: int) -> TypeShape:
        fields: dict[str, FieldShape] = {}
        for prop in body.named_children:
            if prop.type != "property_signature":
                continue
            key = prop.child_by_field_name("name")
            if key is None:
                continue
            optional = any(child.type == "?" for child in prop.children)
            type_node = prop.child_by_field_name("type")
            inner = self.annotation(type_node) if type_node is not None else Annotation()
            fields[string_value(key) or node_text(key)] = self._field(not optional, inner, depth)
        return TypeShape(name, fields)

    def _zod_shape(self, name: str, value: Node, depth: int) -> TypeShape | None:
        base = _zod_base(value)
        if base is None or base[0] != "object":
            return None
        args = base[1].child_by_field_name("arguments")
        objects = [a for a in args.named_children if a.type == "object"] if args else []
        literal = objects[0] if objects else None
        if literal is None:
            return None
        fields: dict[str, FieldShape] = {}
        for pair in literal.named_children:
            if pair.type != "pair":
                continue
            key, item = pair.child_by_field_name("key"), pair.child_by_field_name("value")
            if key is None or item is None:
                continue
            optional = bool(_zod_methods(item) & _ZOD_OPTIONAL)
            fields[string_value(key) or node_text(key)] = self._field(
                not optional, self._zod_annotation(item, depth + 1), depth
            )
        return TypeShape(name, fields)

    def _zod_annotation(self, value: Node, depth: int) -> Annotation:
        """What a Zod expression describes: an object, an array of something, or a schema name."""
        if value.type == "identifier":
            return Annotation(shape=self.shape(node_text(value), depth), present=True)
        base = _zod_base(value)
        if base is None:
            return Annotation(present=True)
        kind, call = base
        if kind == "object":
            return Annotation(shape=self._zod_shape("(object)", call, depth), present=True)
        args = call.child_by_field_name("arguments")
        first = args.named_children[0] if args is not None and args.named_children else None
        if kind == "array" and first is not None:
            inner = self._zod_annotation(first, depth)
            return Annotation(shape=inner.shape, items=True, present=True)
        return Annotation(present=True, primitive=kind in ("string", "number", "boolean"))

    @staticmethod
    def _field(required: bool, inner: Annotation, depth: int) -> FieldShape:
        if inner.items:
            return FieldShape(required=required, item=inner.shape)
        return FieldShape(required=required, nested=inner.shape)


def _declarations(root: Node) -> list[Node]:
    """Top-level statements, with ``export`` unwrapped."""
    found = []
    for node in root.named_children:
        if node.type == "export_statement":
            declaration = node.child_by_field_name("declaration")
            found.append(declaration if declaration is not None else node)
        else:
            found.append(node)
    return found


def _walk(node: Node) -> list[Node]:
    out, stack = [], [node]
    while stack:
        current = stack.pop()
        out.append(current)
        stack.extend(current.named_children)
    return out


def _type_name(node: Node) -> tuple[str, list[Node]]:
    """``("Array", [R])`` for ``Array<R>``; ``("infer", [...])`` for ``z.infer<...>``."""
    if node.type == "type_identifier":
        return node_text(node), []
    if node.type == "nested_type_identifier":
        name = node.child_by_field_name("name")
        return (node_text(name) if name is not None else ""), []
    if node.type == "generic_type":
        name = node.child_by_field_name("name")
        args = node.child_by_field_name("type_arguments")
        base, _ = _type_name(name) if name is not None else ("", [])
        return base, list(args.named_children) if args is not None else []
    return "", []


def _zod_methods(value: Node) -> set[str]:
    """The methods chained on a Zod expression (``z.array(x).optional()``: array, optional)."""
    methods: set[str] = set()
    node = value
    while node.type == "call_expression":
        callee = node.child_by_field_name("function")
        if callee is None or callee.type != "member_expression":
            break
        prop = callee.child_by_field_name("property")
        if prop is not None:
            methods.add(node_text(prop))
        obj = callee.child_by_field_name("object")
        if obj is None:
            break
        node = obj
    return methods


def _zod_base(value: Node) -> tuple[str, Node] | None:
    """The ``z.<kind>(...)`` call at the start of a Zod expression, and its kind."""
    node = value
    while node.type == "call_expression":
        callee = node.child_by_field_name("function")
        if callee is None or callee.type != "member_expression":
            return None
        obj = callee.child_by_field_name("object")
        prop = callee.child_by_field_name("property")
        if obj is not None and obj.type == "identifier" and node_text(obj) == "z":
            return (node_text(prop) if prop is not None else ""), node
        if obj is None:
            return None
        node = obj
    return None


def _resolve(source: Path, spec: str) -> Path | None:
    """The file a relative import names; ``./agents.js`` may be written for ``agents.ts``."""
    target = (source.parent / spec).resolve()
    candidates = [target]
    stem = target.with_suffix("") if target.suffix in _SUFFIXES else target
    candidates += [stem.with_name(stem.name + suffix) for suffix in _SUFFIXES]
    candidates += [stem / f"index{suffix}" for suffix in _SUFFIXES]
    return next((c for c in candidates if c.is_file()), None)


_CACHE: dict[tuple[Path, int], TsModule | None] = {}


def _load(path: Path | None, parser: Parser) -> TsModule | None:
    """Parse an imported file once per version of it."""
    if path is None:
        return None
    try:
        key = (path, path.stat().st_mtime_ns)
    except OSError:
        return None
    if key not in _CACHE:
        try:
            tree = parser.parse(path.read_bytes())
        except OSError:
            _CACHE[key] = None
        else:
            _CACHE[key] = TsModule(path, tree.root_node, parser)
    return _CACHE[key]

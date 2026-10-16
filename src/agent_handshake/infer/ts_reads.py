"""Which input fields a TypeScript or JavaScript function body reads."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from agent_handshake.infer.consumer import FieldRead
from agent_handshake.infer.paths import ITEMS, dotted
from agent_handshake.infer.shapes import Annotation, undeclared
from agent_handshake.infer.ts_syntax import (
    is_optional,
    node_key,
    node_line,
    node_text,
    parameters,
    string_value,
)

if TYPE_CHECKING:
    from tree_sitter import Node

    from agent_handshake.infer.ts_types import TsModule

Chain = tuple[tuple[str, ...], tuple[bool, ...]]

# Wrappers that do not change which value an expression refers to.
_TRANSPARENT = frozenset(
    {"parenthesized_expression", "non_null_expression", "as_expression", "satisfies_expression"}
)
# Array methods whose callback gets each item; reduce passes the item second.
_ITEM_CALLBACKS = {
    "map": 0, "forEach": 0, "filter": 0, "find": 0, "findLast": 0, "findIndex": 0,
    "some": 0, "every": 0, "flatMap": 0, "reduce": 1, "reduceRight": 1,
}  # fmt: skip
# Array methods that return items of the same array.
_ITEM_COPIES = frozenset({"slice", "filter", "concat", "toSorted", "toReversed", "sort", "reverse"})
# How many levels of helper functions are followed.
_MAX_HELPER_DEPTH = 3


@dataclass(frozen=True)
class TsScope:
    """Where helper functions are looked up: the functions and methods of the file."""

    module: TsModule
    helpers: dict[str, Node]
    depth: int = 0
    active: frozenset[str] = frozenset()


class ReadVisitor:
    """Records key chains rooted at the input parameter or at a local alias of it."""

    def __init__(
        self,
        param: str | None,
        annotation: Annotation | None = None,
        scope: TsScope | None = None,
        root: Chain = ((), ()),
    ) -> None:
        self.param = param
        # In a helper function, the parameter holds the part of the input at ``root``.
        self.root = root
        self.scope = scope
        annotation = annotation or Annotation()
        # A list parameter holds one output per item; a framework result holds
        # the output in one property (``runResult.finalOutput``).
        self.items = annotation.items
        self.wrapper = annotation.wrapper
        self.shape = annotation.shape
        self.aliases: dict[str, Chain] = {}
        self.reads: list[FieldRead] = []
        self.warnings: list[str] = []
        # An alias may hold a leaf value, so using it as a whole is only worth
        # a warning when the code also reads keys from it.
        self._mapping_aliases: set[tuple[str, Chain]] = set()
        self._whole_alias_uses: list[tuple[str, Chain, int]] = []

    def finish(self, check_shape: bool = True) -> None:
        for name, chain, line in self._whole_alias_uses:
            if (name, chain) in self._mapping_aliases:
                self._warn_at(line, chain, "is used as a whole")
        if check_shape:
            self.warnings += undeclared(self.reads, self.shape)

    def _is_param(self, node: Node) -> bool:
        node = _unwrap(node)
        return node.type == "identifier" and node_text(node) == self.param

    # -- resolving expressions to key chains ---------------------------------

    def chain(self, node: Node) -> Chain | None:
        """The key chain an expression reads, or None if it is not rooted in the input."""
        if node.type in _TRANSPARENT and node.named_children:
            return self.chain(node.named_children[0])
        if node.type == "identifier":
            name = node_text(node)
            if name == self.param:
                # A list of outputs or a framework result is not the output itself.
                return None if self.items or self.wrapper else self.root
            return self.aliases.get(name)
        if node.type in ("member_expression", "subscript_expression"):
            key = node_key(node)
            obj = node.child_by_field_name("object")
            index = node.child_by_field_name("index")
            by_number = index is not None and index.type == "number"
            if obj is not None and self._is_param(obj):
                if self.items and by_number:
                    return self.root  # an item of a list of outputs
                if self.wrapper and key == self.wrapper:
                    return self.root
            if obj is None:
                return None
            if key is None:
                base = self._base(obj) if by_number else None
                return self._extend(base, ITEMS, optional=False) if base and base[0] else None
            base = self._base(obj)
            if base is None:
                return None
            return self._extend(base, key, optional=is_optional(node))
        return None

    def _base(self, node: Node) -> Chain | None:
        """Resolve an expression that keys are read from, noting aliases used as mappings."""
        inner = _unwrap(node)
        if inner.type == "identifier" and node_text(inner) in self.aliases:
            self._mapping_aliases.add((node_text(inner), self.aliases[node_text(inner)]))
        return self.chain(node)

    def _items_of(self, node: Node) -> Chain | None:
        """The chain of one item of the input list ``node`` refers to.

        The parameter itself, when it is a list of outputs, gives the root.
        """
        inner = _unwrap(node)
        if self.items and self._is_param(inner):
            return self.root
        chain = self.chain(inner) or self._held(inner)
        return ((*chain[0], ITEMS), (*chain[1], False)) if chain and chain[0] else None

    def _held(self, node: Node) -> Chain | None:
        """The input part ``x ?? {}`` or ``x || []`` passes on; it may be missing."""
        node = _unwrap(node)
        if node.type != "binary_expression":
            return None
        operator = node.child_by_field_name("operator")
        left = node.child_by_field_name("left")
        if operator is None or left is None or node_text(operator) not in ("??", "||"):
            return None
        chain = self.chain(left)
        return (chain[0], (*chain[1][:-1], False)) if chain and chain[0] else None

    def _bind(self, target: Node | None, chain: Chain | None) -> None:
        """Bind a name to a part of the input, or unbind it."""
        if target is None or target.type != "identifier":
            return
        if chain is None:
            self.aliases.pop(node_text(target), None)
        else:
            self.aliases[node_text(target)] = chain

    @staticmethod
    def _extend(base: Chain, key: str, optional: bool) -> Chain:
        """Add ``key``; reading through the previous key without ``?.`` makes it strict."""
        path, strict = base
        if path and not optional:
            strict = (*strict[:-1], True)
        return (*path, key), (*strict, False)

    @staticmethod
    def _used(chain: Chain, optional: bool = False) -> Chain:
        """The chain of a value that is used in a way that throws when it is missing."""
        path, strict = chain
        if path and not optional:
            strict = (*strict[:-1], True)
        return path, strict

    def _record(self, chain: Chain, node: Node) -> None:
        if chain[0]:
            self.reads.append(FieldRead(chain[0], node_line(node), chain[1]))

    # -- visiting --------------------------------------------------------------

    def visit(self, node: Node) -> None:
        handler = getattr(self, f"_visit_{node.type}", None)
        if handler is not None:
            handler(node)
        else:
            for child in node.named_children:
                self.visit(child)

    def _visit_member_expression(self, node: Node) -> None:
        obj = node.child_by_field_name("object")
        if obj is None:
            return
        base = self._base(obj)
        if base is not None and base[0] and node_key(node) == "length":
            # .length of a string or array is not a field of the input.
            if base[0][-1] != ITEMS:
                self._record(self._used(base, is_optional(node)), node)
            return
        chain = self.chain(node)
        if chain is not None:
            self._record(chain, node)
            return
        self.visit(obj)

    def _visit_subscript_expression(self, node: Node) -> None:
        chain = self.chain(node)
        if chain is not None:
            self._record(chain, node)
            return
        obj = node.child_by_field_name("object")
        index = node.child_by_field_name("index")
        base = self._base(obj) if obj is not None else None
        if base is None:
            for child in node.named_children:
                self.visit(child)
            return
        # Rooted in the input, but the key is not a string literal.
        if not (base[0] and index is not None and index.type == "number"):
            self._warn(node, "reads a non-literal key", base)
        self._record(self._used(base, is_optional(node)), node)
        if index is not None:
            self.visit(index)

    def _visit_call_expression(self, node: Node) -> None:
        callee = node.child_by_field_name("function")
        args = node.child_by_field_name("arguments")
        followed = self._follow(callee, args)
        if followed is not None:
            for arg in args.named_children if args is not None else []:
                if arg.id not in followed:
                    self.visit(arg)
            return
        for arg in args.named_children if args is not None else []:
            chain = self.chain(arg) if _unwrap(arg).type == "identifier" else None
            if chain is not None and chain[0] and chain[0][-1] == ITEMS:
                # A list item given to a function that is not followed.
                self.warnings.append(
                    f"line {node_line(arg)}: '{node_text(_unwrap(arg))}' is an item of "
                    f"'{dotted(chain[0][:-1])}' and goes to a function that is not followed; "
                    "the inferred contract may be incomplete"
                )
        found = self._callback_item(callee, args)
        if found is None:
            self._visit_call(node, callee, args)
            return
        item, chain = found
        # The callback's item name is local to the callback.
        name = node_text(item)
        before = self.aliases.get(name)
        self._bind(item, chain)
        try:
            self._visit_call(node, callee, args)
        finally:
            self.aliases.pop(name, None)
            if before is not None:
                self.aliases[name] = before

    def _callback_item(self, callee: Node | None, args: Node | None) -> tuple[Node, Chain] | None:
        """The item parameter of an array callback over an input list (``xs.map(x => ...)``)."""
        if callee is None or callee.type != "member_expression" or args is None:
            return None
        obj = callee.child_by_field_name("object")
        chain = self._items_of(obj) if obj is not None else None
        if chain is None or node_key(callee) not in _ITEM_CALLBACKS:
            return None
        callbacks = [a for a in args.named_children if a.type in _FUNCTIONS]
        if not callbacks:
            return None
        params = [p for p, _ in parameters(callbacks[0])]
        position = _ITEM_CALLBACKS[node_key(callee) or ""]
        item = params[position] if len(params) > position else None
        return (item, chain) if item is not None and item.type == "identifier" else None

    def _follow(self, callee: Node | None, args: Node | None) -> set[int] | None:
        """Read a helper in the same file that gets a part of the input.

        Returns the ids of the arguments whose reads were followed, or None.
        """
        scope = self.scope
        if scope is None or callee is None or args is None or scope.depth >= _MAX_HELPER_DEPTH:
            return None
        if callee.type == "identifier":
            name = node_text(callee)
        elif (
            callee.type == "member_expression"
            and node_text(callee.child_by_field_name("object") or callee) == "this"
        ):
            name = node_key(callee) or ""
        else:
            return None
        helper = scope.helpers.get(name)
        if helper is None or name in scope.active:
            return None
        inner = replace(scope, depth=scope.depth + 1, active=scope.active | {name})
        body = helper.child_by_field_name("body")
        followed: set[int] = set()
        for arg, (pattern, type_node) in zip(args.named_children, parameters(helper), strict=False):
            chain = self.chain(arg)
            if chain is None:
                continue
            annotation = scope.module.annotation(type_node)
            if pattern.type == "identifier":
                child = ReadVisitor(node_text(pattern), annotation, inner, root=chain)
            else:
                child = ReadVisitor(None, scope=inner, root=chain)
                child.destructure(pattern, chain)
            if body is not None:
                child.visit(body)
            child.finish(check_shape=False)
            inner_arg = _unwrap(arg)
            if not (inner_arg.type == "identifier" and node_text(inner_arg) in self.aliases):
                self._record(self._used(chain), arg)  # an alias was recorded when bound
            self.reads += child.reads
            self.warnings += [w for w in child.warnings if w not in self.warnings]
            followed.add(arg.id)
        return followed if followed else None

    def _visit_call(self, node: Node, callee: Node | None, args: Node | None) -> None:
        if callee is not None and callee.type == "member_expression":
            obj = callee.child_by_field_name("object")
            method = node_key(callee)
            base = self._base(obj) if obj is not None else None
            if base is not None:
                if not base[0]:
                    self._warn(node, f"calls .{method}()", base)
                elif base[0][-1] != ITEMS:
                    # A method of a string or array value, not a field of the input.
                    self._record(self._used(base, is_optional(callee)), node)
                if args is not None:
                    self.visit(args)
                return
        for child in node.named_children:
            self.visit(child)

    def _visit_binary_expression(self, node: Node) -> None:
        operator = node.child_by_field_name("operator")
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if (
            operator is not None
            and node_text(operator) == "in"
            and left is not None
            and right is not None
            and string_value(left) is not None
        ):
            key = string_value(left) or ""
            base = self._base(right)
            if base is not None:
                self._record(self._extend(base, key, optional=False), node)
                return
        for child in node.named_children:
            self.visit(child)

    def _visit_variable_declarator(self, node: Node) -> None:
        name = node.child_by_field_name("name")
        value = node.child_by_field_name("value")
        if value is None or name is None:
            return
        chain = self.chain(value)
        if name.type == "identifier":
            self.visit(value)
            held = chain if chain is not None else self._held(value) or self._copied_list(value)
            self._bind(name, held if held is not None and held[0] else None)
        elif name.type == "object_pattern" and chain is not None:
            self.destructure(name, chain)
        else:
            self.visit(value)

    def _copied_list(self, value: Node) -> Chain | None:
        """The input list that ``value`` copies, as in ``data.items.slice(0, 3)``."""
        value = _unwrap(value)
        if value.type != "call_expression":
            return None
        callee = value.child_by_field_name("function")
        if callee is None or callee.type != "member_expression":
            return None
        obj = callee.child_by_field_name("object")
        if node_key(callee) not in _ITEM_COPIES or obj is None:
            return None
        chain = self.chain(obj)
        return chain if chain is not None and chain[0] else None

    def _visit_for_in_statement(self, node: Node) -> None:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        operator = node.child_by_field_name("operator")
        if right is not None:
            self.visit(right)
        if operator is not None and node_text(operator) == "of" and right is not None:
            self._bind(left, self._items_of(right))
        body = node.child_by_field_name("body")
        if body is not None:
            self.visit(body)

    def _visit_assignment_expression(self, node: Node) -> None:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if right is not None:
            self.visit(right)
        if left is None:
            return
        if left.type == "identifier":
            if node_text(left) == self.param:
                self._warn(left, "is reassigned")
            else:
                self.aliases.pop(node_text(left), None)
        elif left.type in ("member_expression", "subscript_expression"):
            obj = left.child_by_field_name("object")
            if obj is not None and self.chain(obj) is None:
                self.visit(obj)  # a write into the input is not a read

    def _visit_identifier(self, node: Node) -> None:
        self._whole_use(node, node_text(node))

    def _visit_shorthand_property_identifier(self, node: Node) -> None:
        self._whole_use(node, node_text(node))  # { data } in an object literal

    def _visit_formal_parameters(self, node: Node) -> None:
        """Parameters of a nested function declare names; they do not read the input."""

    def _visit_arrow_function(self, node: Node) -> None:
        """``x => ...`` declares ``x``; only the body can read the input."""
        body = node.child_by_field_name("body")
        if body is not None:
            self.visit(body)

    def _whole_use(self, node: Node, name: str) -> None:
        if name == self.param:
            self._warn(node, "is used as a whole", self.root)
        elif name in self.aliases:
            self._whole_alias_uses.append((name, self.aliases[name], node_line(node)))

    # -- destructuring ----------------------------------------------------------

    def destructure(self, pattern: Node, base: Chain, has_default: bool = False) -> None:
        """Record the keys an object pattern takes from the value at ``base``.

        Destructuring ``undefined`` throws, so ``base`` becomes strict unless
        the pattern has a default (``{ customer: { tier } = {} }``).
        """
        if not has_default:
            base = self._used(base)
        for item in pattern.named_children:
            if item.type == "shorthand_property_identifier_pattern":
                self._take(item, base, node_text(item), item, optional=False)
            elif item.type == "object_assignment_pattern":
                left = item.child_by_field_name("left")
                right = item.child_by_field_name("right")
                if left is not None:
                    self._take(item, base, node_text(left), left, optional=True)
                if right is not None:
                    self.visit(right)
            elif item.type == "pair_pattern":
                key_node = item.child_by_field_name("key")
                value = item.child_by_field_name("value")
                key = string_value(key_node) if key_node is not None else None
                if key_node is not None and key is None and key_node.type == "property_identifier":
                    key = node_text(key_node)
                if key is None or value is None:
                    self._warn(item, "destructures a non-literal key", base)
                    continue
                optional = value.type == "assignment_pattern"
                target = value.child_by_field_name("left") if optional else value
                if optional:
                    default = value.child_by_field_name("right")
                    if default is not None:
                        self.visit(default)
                if target is not None:
                    self._take(item, base, key, target, optional=optional)
            elif item.type == "rest_pattern":
                self._warn(item, "collects the remaining keys", base)

    def _take(self, at: Node, base: Chain, key: str, target: Node, optional: bool) -> None:
        """Record ``key`` from ``base`` and bind or destructure it into ``target``."""
        chain: Chain = ((*base[0], key), (*base[1], False))
        if target.type == "object_pattern":
            self.destructure(target, chain, has_default=optional)
            return
        self._record(chain, at)
        if target.type in ("identifier", "shorthand_property_identifier_pattern"):
            self.aliases[node_text(target)] = chain

    # -- warnings ----------------------------------------------------------------

    def _warn(self, node: Node, what: str, chain: Chain | None = None) -> None:
        self._warn_at(node_line(node), chain, what)

    def _warn_at(self, line: int, chain: Chain | None, what: str) -> None:
        label = f"'{dotted(chain[0])}'" if chain and chain[0] else f"'{self.param or 'input'}'"
        self.warnings.append(
            f"line {line}: {label} {what}; the inferred contract may be incomplete"
        )


_FUNCTIONS = frozenset({"arrow_function", "function_expression", "function"})


def _unwrap(node: Node) -> Node:
    while node.type in _TRANSPARENT and node.named_children:
        node = node.named_children[0]
    return node

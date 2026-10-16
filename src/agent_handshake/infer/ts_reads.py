"""Which input fields a TypeScript or JavaScript function body reads."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_handshake.infer.consumer import FieldRead
from agent_handshake.infer.ts_syntax import (
    is_optional,
    node_key,
    node_line,
    node_text,
    string_value,
)

if TYPE_CHECKING:
    from tree_sitter import Node

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


class ReadVisitor:
    """Records key chains rooted at the input parameter or at a local alias of it."""

    def __init__(self, param: str | None) -> None:
        self.param = param
        self.aliases: dict[str, Chain] = {}
        self.reads: list[FieldRead] = []
        self.warnings: list[str] = []
        # An alias may hold a leaf value, so using it as a whole is only worth
        # a warning when the code also reads keys from it.
        self._mapping_aliases: set[str] = set()
        self._whole_alias_uses: list[tuple[str, Chain, int]] = []
        # Names that hold list items of the input, which the analysis does not
        # follow; reading keys from them, or passing them on, gets a warning.
        self._untracked: dict[str, str] = {}
        # Names that hold a copy of an input list (``data.items.slice(0, 3)``).
        self._item_lists: dict[str, Chain] = {}

    def finish(self) -> None:
        for name, chain, line in self._whole_alias_uses:
            if name in self._mapping_aliases:
                self._warn_at(line, chain, "is used as a whole")

    # -- resolving expressions to key chains ---------------------------------

    def chain(self, node: Node) -> Chain | None:
        """The key chain an expression reads, or None if it is not rooted in the input."""
        if node.type in _TRANSPARENT and node.named_children:
            return self.chain(node.named_children[0])
        if node.type == "identifier":
            name = node_text(node)
            if name == self.param:
                return (), ()
            return self.aliases.get(name)
        if node.type in ("member_expression", "subscript_expression"):
            key = node_key(node)
            obj = node.child_by_field_name("object")
            if key is None or obj is None:
                return None
            base = self._base(obj)
            if base is None:
                return None
            return self._extend(base, key, optional=is_optional(node))
        return None

    def _base(self, node: Node) -> Chain | None:
        """Resolve an expression that keys are read from, noting aliases used as mappings."""
        inner = _unwrap(node)
        if inner.type == "identifier" and node_text(inner) in self.aliases:
            self._mapping_aliases.add(node_text(inner))
        self._check_untracked(inner)
        return self.chain(node)

    def _list(self, node: Node) -> Chain | None:
        """The input list an expression refers to, directly or as a copy of it."""
        inner = _unwrap(node)
        if inner.type == "identifier" and node_text(inner) in self._item_lists:
            return self._item_lists[node_text(inner)]
        chain = self.chain(inner)
        return chain if chain is not None and chain[0] else None

    def _check_untracked(self, node: Node) -> None:
        """Warn once when list items of the input are read from or passed on."""
        node = _unwrap(node)
        parent = node.parent
        if parent is not None and parent.type == "member_expression":
            if node_key(parent) == "length":
                return  # the length of a string or list item is not a field
        if node.type == "identifier" and node_text(node) in self._untracked:
            how = self._untracked.pop(node_text(node))
            self._warn_text(node_line(node), f"'{node_text(node)}' {how}")
        elif node.type == "subscript_expression":
            obj = node.child_by_field_name("object")
            index = node.child_by_field_name("index")
            listed = self._list(obj) if obj is not None else None
            if listed is not None and index is not None and index.type == "number":
                self._warn_text(node_line(node), f"an item of '{'.'.join(listed[0])}' is read")

    def _is_untracked(self, node: Node) -> bool:
        return node.type == "identifier" and node_text(node) in self._untracked

    def _bind_items(self, target: Node | None, listed: Chain | None) -> None:
        """Note a name that takes the items of an input list."""
        if target is None or target.type != "identifier":
            return
        name = node_text(target)
        self.aliases.pop(name, None)
        if listed is not None:
            self._untracked[name] = f"is an item of '{'.'.join(listed[0])}'"
        else:
            self._untracked.pop(name, None)

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
        if args is not None:
            for arg in args.named_children:
                self._check_untracked(arg)
        if callee is not None and callee.type == "member_expression":
            obj = callee.child_by_field_name("object")
            method = node_key(callee)
            listed = self._list(obj) if obj is not None else None
            if listed is not None and method in _ITEM_CALLBACKS and args is not None:
                callbacks = [a for a in args.named_children if a.type in _FUNCTIONS]
                if callbacks:
                    params = _parameters(callbacks[0])
                    position = _ITEM_CALLBACKS[method]
                    item = params[position] if len(params) > position else None
                    self._bind_items(item, listed)
            inner = _unwrap(obj) if obj is not None else None
            if inner is not None and self._is_untracked(inner):
                # A method of a list item (a string or an object): not a key read.
                if args is not None:
                    self.visit(args)
                return
            base = self._base(obj) if obj is not None else None
            if base is not None:
                if not base[0]:
                    self._warn(node, f"calls .{method}()", base)
                else:
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
            self._untracked.pop(node_text(name), None)
            self._item_lists.pop(node_text(name), None)
            if chain is not None and chain[0]:
                self.aliases[node_text(name)] = chain
            else:
                self.aliases.pop(node_text(name), None)
                copied = self._copied_list(value)
                if copied is not None:
                    self._item_lists[node_text(name)] = copied
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
        return self._list(obj)

    def _visit_for_in_statement(self, node: Node) -> None:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        operator = node.child_by_field_name("operator")
        if right is not None:
            self.visit(right)
        if operator is not None and node_text(operator) == "of" and right is not None:
            self._bind_items(left, self._list(right))
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

    def _whole_use(self, node: Node, name: str) -> None:
        if name == self.param:
            self._warn(node, "is used as a whole", ((), ()))
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

    def _warn_text(self, line: int, what: str) -> None:
        warning = (
            f"line {line}: {what}, and its keys are not followed; "
            "the inferred contract may be incomplete"
        )
        if warning not in self.warnings:
            self.warnings.append(warning)

    def _warn_at(self, line: int, chain: Chain | None, what: str) -> None:
        label = f"'{'.'.join(chain[0])}'" if chain and chain[0] else f"'{self.param or 'input'}'"
        self.warnings.append(
            f"line {line}: {label} {what}; the inferred contract may be incomplete"
        )


_FUNCTIONS = frozenset({"arrow_function", "function_expression", "function"})


def _unwrap(node: Node) -> Node:
    while node.type in _TRANSPARENT and node.named_children:
        node = node.named_children[0]
    return node


def _parameters(function: Node) -> list[Node]:
    """The names a callback declares, in order (``x => ...`` or ``(x, i) => ...``)."""
    single = function.child_by_field_name("parameter")
    if single is not None:
        return [single]
    params = function.child_by_field_name("parameters")
    if params is None:
        return []
    names = []
    for param in params.named_children:
        pattern = param.child_by_field_name("pattern") or param
        names.append(pattern)
    return names

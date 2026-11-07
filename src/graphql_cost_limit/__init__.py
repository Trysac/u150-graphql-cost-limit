"""Schema-aware cost and depth limits for GraphQL queries."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from graphql import (
    FieldNode,
    FragmentSpreadNode,
    GraphQLCompositeType,
    GraphQLNamedType,
    GraphQLSchema,
    GraphQLSyntaxError,
    InlineFragmentNode,
    OperationDefinitionNode,
    build_schema,
    get_named_type,
    get_nullable_type,
    is_leaf_type,
    is_list_type,
    parse,
)

__all__ = [
    "Analysis",
    "CostConfig",
    "CostLimitError",
    "ErrorCode",
    "__version__",
    "analyze",
    "check",
]

__version__ = "0.1.0"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

ErrorCode = Literal[
    "query_too_large",
    "too_deep_nesting",
    "syntax_error",
    "operation_required",
    "unknown_operation",
    "fragment_cycle",
    "unknown_field",
    "invalid_argument",
    "max_cost",
    "max_depth",
]


class CostLimitError(Exception):
    """Raised when query analysis fails or cost/depth exceeds configured limits."""

    def __init__(
        self,
        message: str,
        code: ErrorCode,
        *,
        cost: int | None = None,
        limit: int | None = None,
    ) -> None:
        if len(message) > 200:
            message = message[:200]
        super().__init__(message)
        self.code: ErrorCode = code
        self.cost: int | None = cost
        self.limit: int | None = limit


@dataclass(frozen=True)
class CostConfig:
    """Configuration settings for GraphQL cost and depth analysis."""

    field_costs: Mapping[str, int] = field(default_factory=dict)
    default_object_cost: int = 1
    default_leaf_cost: int = 0
    slicing_arguments: tuple[str, ...] = ("first", "last", "limit")
    default_list_size: int = 10
    max_cost: int = 1000
    max_depth: int = 10
    max_query_chars: int = 100_000
    max_nesting: int = 100


@dataclass(frozen=True)
class Analysis:
    """Result of query cost and depth calculation."""

    cost: int
    depth: int


DEFAULT_COST_CONFIG = CostConfig()


def _check_nesting(query: str, max_nesting: int) -> None:
    """Check nesting of curly braces outside strings and comments."""
    depth = 0
    i = 0
    n = len(query)
    while i < n:
        c = query[i]
        if c == "#":
            # Comment runs to newline
            i += 1
            while i < n and query[i] != "\n" and query[i] != "\r":
                i += 1
            continue
        elif c == '"':
            # String literal or block string
            if i + 2 < n and query[i : i + 3] == '"""':
                # Block string
                i += 3
                while i < n:
                    if query[i] == "\\":
                        i += 2
                    elif i + 2 < n and query[i : i + 3] == '"""':
                        i += 3
                        break
                    else:
                        i += 1
                continue
            else:
                # Normal string
                i += 1
                while i < n:
                    if query[i] == "\\":
                        i += 2
                    elif query[i] == '"':
                        i += 1
                        break
                    else:
                        i += 1
                continue
        elif c == "{":
            depth += 1
            if depth > max_nesting:
                raise CostLimitError(
                    f"Query nesting depth exceeds maximum allowed nesting of {max_nesting}",
                    code="too_deep_nesting",
                )
        elif c == "}" and depth > 0:
            depth -= 1
        i += 1


def _is_list_wrapped(type_: Any) -> bool:
    """Check if type or any inner type before named type is a list."""
    curr = get_nullable_type(type_)
    while curr is not None and not isinstance(curr, GraphQLNamedType):
        if is_list_type(curr):
            return True
        curr = get_nullable_type(getattr(curr, "of_type", None))
    return False


def _extract_arg_value(
    arg_value_node: Any,
    variables: Mapping[str, Any] | None,
) -> Any:
    """Extract value from AST argument node, resolving variables."""
    from graphql.language.ast import VariableNode

    if isinstance(arg_value_node, VariableNode):
        var_name = arg_value_node.name.value
        if variables is not None and var_name in variables:
            return variables[var_name]
        return None
    # Literal values
    val = getattr(arg_value_node, "value", None)
    if val is not None:
        try:
            return int(val)
        except (ValueError, TypeError):
            return val
    return None


def analyze(
    query: str,
    schema: GraphQLSchema | str,
    *,
    variables: Mapping[str, Any] | None = None,
    operation_name: str | None = None,
    config: CostConfig = DEFAULT_COST_CONFIG,
) -> Analysis:
    """Analyze the cost and depth of a GraphQL query against a schema."""
    # 1. Length check
    if len(query) > config.max_query_chars:
        raise CostLimitError(
            f"Query character length {len(query)} exceeds maximum of {config.max_query_chars}",
            code="query_too_large",
        )

    # 2. Pre-parse nesting scan
    _check_nesting(query, config.max_nesting)

    # 3. Parse query
    try:
        document = parse(query)
    except GraphQLSyntaxError as err:
        raise CostLimitError(
            f"Syntax error in query: {err.message}",
            code="syntax_error",
        ) from err

    # Schema conversion if string
    gql_schema = build_schema(schema) if isinstance(schema, str) else schema

    # Collect operations and fragments
    operations: list[OperationDefinitionNode] = []
    fragments: dict[str, Any] = {}

    for definition in document.definitions:
        if isinstance(definition, OperationDefinitionNode):
            operations.append(definition)
        elif (
            hasattr(definition, "name") and getattr(definition, "kind", "") == "fragment_definition"
        ):
            fragments[definition.name.value] = definition

    # 4. Operation selection
    if not operations:
        raise CostLimitError("No operations in query document", code="syntax_error")

    target_operation: OperationDefinitionNode | None = None
    if operation_name is not None:
        for op in operations:
            if op.name and op.name.value == operation_name:
                target_operation = op
                break
        if target_operation is None:
            raise CostLimitError(
                f"Unknown operation '{operation_name}'",
                code="unknown_operation",
            )
    else:
        if len(operations) > 1:
            raise CostLimitError(
                "Multiple operations present; operation_name is required",
                code="operation_required",
            )
        target_operation = operations[0]

    # Determine root type
    op_type = target_operation.operation.value
    root_type: GraphQLCompositeType | None = None
    if op_type == "query":
        root_type = gql_schema.query_type
    elif op_type == "mutation":
        root_type = gql_schema.mutation_type
    elif op_type == "subscription":
        root_type = gql_schema.subscription_type

    if root_type is None:
        raise CostLimitError(
            f"Schema has no root type for operation '{op_type}'",
            code="unknown_field",
        )

    # 5. Walk selection set
    def walk_selection_set(
        selection_set: Any,
        parent_type: Any,
        visiting_fragments: set[str],
    ) -> tuple[int, int]:
        total_cost = 0
        max_child_depth = 0

        for selection in selection_set.selections:
            if isinstance(selection, FieldNode):
                field_name = selection.name.value
                # __typename costs 0 and adds no depth
                if field_name == "__typename":
                    continue

                # Get field definition from parent_type
                named_parent = get_named_type(parent_type)
                fields = getattr(named_parent, "fields", None)
                if fields is None or field_name not in fields:
                    parent_display = getattr(named_parent, "name", str(named_parent))
                    raise CostLimitError(
                        f"Unknown field '{field_name}' on type '{parent_display}'",
                        code="unknown_field",
                    )

                field_def = fields[field_name]
                field_type = field_def.type
                named_field_type = get_named_type(field_type)

                # Field cost calculation
                parent_name = getattr(named_parent, "name", "")
                field_key = f"{parent_name}.{field_name}"
                if field_key in config.field_costs:
                    field_cost = config.field_costs[field_key]
                elif is_leaf_type(named_field_type):
                    field_cost = config.default_leaf_cost
                else:
                    field_cost = config.default_object_cost

                # Multiplier calculation for lists
                is_list = _is_list_wrapped(field_type)
                if is_list:
                    multiplier = None
                    for slicing_arg in config.slicing_arguments:
                        arg_node = next(
                            (a for a in selection.arguments if a.name.value == slicing_arg),
                            None,
                        )
                        if arg_node is not None:
                            val = _extract_arg_value(arg_node.value, variables)
                            if val is not None:
                                if isinstance(val, bool) or not isinstance(val, int) or val < 0:
                                    msg = (
                                        f"Slicing argument '{slicing_arg}' must be an "
                                        f"integer >= 0, got {val!r}"
                                    )
                                    raise CostLimitError(msg, code="invalid_argument")
                                multiplier = val
                                break
                    if multiplier is None:
                        multiplier = config.default_list_size
                else:
                    multiplier = 1

                # Children cost and depth
                child_cost = 0
                child_depth = 0
                if selection.selection_set is not None:
                    c_cost, c_depth = walk_selection_set(
                        selection.selection_set,
                        named_field_type,
                        visiting_fragments,
                    )
                    child_cost = c_cost
                    child_depth = c_depth

                total_cost += field_cost + multiplier * child_cost
                field_depth = 1 + child_depth
                if field_depth > max_child_depth:
                    max_child_depth = field_depth

            elif isinstance(selection, FragmentSpreadNode):
                frag_name = selection.name.value
                if frag_name in visiting_fragments:
                    raise CostLimitError(
                        f"Fragment cycle detected at '{frag_name}'",
                        code="fragment_cycle",
                    )
                frag_def = fragments.get(frag_name)
                if frag_def is None:
                    raise CostLimitError(
                        f"Unknown fragment '{frag_name}'",
                        code="unknown_field",
                    )
                # New parent type from condition
                cond_name = frag_def.type_condition.name.value
                cond_type = gql_schema.type_map.get(cond_name)
                if cond_type is None:
                    raise CostLimitError(
                        f"Unknown type condition '{cond_name}' in fragment '{frag_name}'",
                        code="unknown_field",
                    )
                new_visiting = visiting_fragments | {frag_name}
                frag_cost, frag_depth = walk_selection_set(
                    frag_def.selection_set,
                    cond_type,
                    new_visiting,
                )
                total_cost += frag_cost
                if frag_depth > max_child_depth:
                    max_child_depth = frag_depth

            elif isinstance(selection, InlineFragmentNode):
                cond_type = parent_type
                if selection.type_condition is not None:
                    cond_name = selection.type_condition.name.value
                    cond_type = gql_schema.type_map.get(cond_name)
                    if cond_type is None:
                        raise CostLimitError(
                            f"Unknown type condition '{cond_name}' in inline fragment",
                            code="unknown_field",
                        )
                frag_cost, frag_depth = walk_selection_set(
                    selection.selection_set,
                    cond_type,
                    visiting_fragments,
                )
                total_cost += frag_cost
                if frag_depth > max_child_depth:
                    max_child_depth = frag_depth

        return total_cost, max_child_depth

    cost, depth = walk_selection_set(target_operation.selection_set, root_type, set())
    return Analysis(cost=cost, depth=depth)


def check(
    query: str,
    schema: GraphQLSchema | str,
    *,
    variables: Mapping[str, Any] | None = None,
    operation_name: str | None = None,
    config: CostConfig = DEFAULT_COST_CONFIG,
) -> Analysis:
    """Analyze query and raise CostLimitError if configured limits are exceeded."""
    analysis = analyze(
        query,
        schema,
        variables=variables,
        operation_name=operation_name,
        config=config,
    )
    if analysis.cost > config.max_cost:
        raise CostLimitError(
            f"Query cost {analysis.cost} exceeds max_cost limit of {config.max_cost}",
            code="max_cost",
            cost=analysis.cost,
            limit=config.max_cost,
        )
    if analysis.depth > config.max_depth:
        raise CostLimitError(
            f"Query depth {analysis.depth} exceeds max_depth limit of {config.max_depth}",
            code="max_depth",
            cost=analysis.depth,
            limit=config.max_depth,
        )
    return analysis

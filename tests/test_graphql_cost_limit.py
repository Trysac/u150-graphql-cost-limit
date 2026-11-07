"""Unit tests for trysac-graphql-cost-limit."""

from __future__ import annotations

import pytest
from graphql import build_schema

from graphql_cost_limit import (
    Analysis,
    CostConfig,
    CostLimitError,
    analyze,
    check,
)

SCHEMA_SDL = """
type Query {
    users(first: Int): [User!]!
    me: User
}
type User {
    id: ID!
    name: String
    friends(first: Int): [User!]!
    posts: [Post!]!
}
type Post {
    title: String
}
"""


def test_acceptance_users_friends_posts_cost_and_depth() -> None:
    schema = build_schema(SCHEMA_SDL)
    query = "{ users(first: 10) { friends(first: 5) { posts { title } } } }"
    result = analyze(query, schema)
    assert result == Analysis(cost=61, depth=4)


def test_acceptance_me_posts_default_list_size() -> None:
    schema = build_schema(SCHEMA_SDL)
    result = analyze("{ me { posts { title } } }", schema)
    assert result.cost == 2


def test_acceptance_query_variable_slicing() -> None:
    schema = build_schema(SCHEMA_SDL)
    result = analyze(
        "query Q($n: Int) { users(first: $n) { posts { title } } }",
        schema,
        variables={"n": 3},
    )
    assert result.cost == 4

    # Missing variable uses default_list_size (10)
    # users 1 + 10 * (posts 1 + 10 * 0) = 1 + 10 = 11
    result_missing = analyze(
        "query Q($n: Int) { users(first: $n) { posts { title } } }",
        schema,
        variables={},
    )
    assert result_missing.cost == 11


def test_acceptance_aliases_and_typename() -> None:
    schema = build_schema(SCHEMA_SDL)
    res_alias = analyze("{ a: me { id } b: me { id } }", schema)
    assert res_alias.cost == 2

    res_typename = analyze("{ __typename me { id } }", schema)
    assert res_typename.cost == 1


def test_acceptance_check_limits() -> None:
    schema = build_schema(SCHEMA_SDL)
    query = "{ users(first: 10) { friends(first: 5) { posts { title } } } }"

    with pytest.raises(CostLimitError) as exc_info:
        check(query, schema, config=CostConfig(max_cost=50))
    assert exc_info.value.code == "max_cost"
    assert exc_info.value.cost == 61
    assert exc_info.value.limit == 50

    with pytest.raises(CostLimitError) as exc_info_depth:
        check(query, schema, config=CostConfig(max_depth=3))
    assert exc_info_depth.value.code == "max_depth"
    assert exc_info_depth.value.cost == 4
    assert exc_info_depth.value.limit == 3


def test_acceptance_fragment_cycle() -> None:
    schema = build_schema(SCHEMA_SDL)
    query = "fragment A on User { ...B } fragment B on User { ...A } { me { ...A } }"
    with pytest.raises(CostLimitError) as exc_info:
        analyze(query, schema)
    assert exc_info.value.code == "fragment_cycle"


def test_acceptance_invalid_argument() -> None:
    schema = build_schema(SCHEMA_SDL)
    with pytest.raises(CostLimitError) as exc_info:
        analyze("{ users(first: -1) { id } }", schema)
    assert exc_info.value.code == "invalid_argument"

    with pytest.raises(CostLimitError) as exc_info_bool:
        analyze("query Q($f: Int) { users(first: $f) { id } }", schema, variables={"f": True})
    assert exc_info_bool.value.code == "invalid_argument"


def test_acceptance_unknown_field() -> None:
    schema = build_schema(SCHEMA_SDL)
    with pytest.raises(CostLimitError) as exc_info:
        analyze("{ unknownField }", schema)
    assert exc_info.value.code == "unknown_field"


def test_acceptance_query_too_large() -> None:
    schema = build_schema(SCHEMA_SDL)
    query = " " * 100_001
    with pytest.raises(CostLimitError) as exc_info:
        analyze(query, schema)
    assert exc_info.value.code == "query_too_large"


def test_acceptance_too_deep_nesting() -> None:
    schema = build_schema(SCHEMA_SDL)
    query = "{" * 101 + "}" * 101
    with pytest.raises(CostLimitError) as exc_info:
        analyze(query, schema)
    assert exc_info.value.code == "too_deep_nesting"


def test_acceptance_syntax_error() -> None:
    schema = build_schema(SCHEMA_SDL)
    with pytest.raises(CostLimitError) as exc_info:
        analyze("invalid graphql query { ", schema)
    assert exc_info.value.code == "syntax_error"


def test_acceptance_operation_selection() -> None:
    schema = build_schema(SCHEMA_SDL)
    two_ops = "query Q1 { me { id } } query Q2 { me { name } }"
    with pytest.raises(CostLimitError) as exc_info:
        analyze(two_ops, schema)
    assert exc_info.value.code == "operation_required"

    with pytest.raises(CostLimitError) as exc_info_unk:
        analyze(two_ops, schema, operation_name="X")
    assert exc_info_unk.value.code == "unknown_operation"

    # Correct selection
    res = analyze(two_ops, schema, operation_name="Q1")
    assert res.cost == 1
    assert res.depth == 2


def test_schema_as_string_and_custom_field_cost() -> None:
    query = "{ me { id } }"
    cfg = CostConfig(field_costs={"User.id": 5})
    res = analyze(query, SCHEMA_SDL, config=cfg)
    assert res.cost == 6  # me (1) + 1 * id (5)


def test_mutation_and_subscription_support() -> None:
    sdl = """
    type Query { me: User }
    type Mutation { updateUser(name: String): User }
    type Subscription { userUpdated: User }
    type User { id: ID! }
    """
    mut = 'mutation M { updateUser(name: "test") { id } }'
    res_mut = analyze(mut, sdl, operation_name="M")
    assert res_mut.cost == 1  # updateUser (1) + id (0)

    sub = "subscription S { userUpdated { id } }"
    res_sub = analyze(sub, sdl)
    assert res_sub.cost == 1


def test_inline_fragment_and_interfaces() -> None:
    sdl = """
    type Query { node: Node }
    interface Node { id: ID! }
    type User implements Node { id: ID! name: String }
    """
    q = "{ node { id ... on User { name } } }"
    res = analyze(q, sdl)
    assert res.cost == 1  # node (1) + id (0) + name (0)
    assert res.depth == 2


def test_comments_and_strings_nesting_scan() -> None:
    # Ensure '{' inside strings or comments does not trigger false nesting
    query = '# { { {\n{ me(arg: " { { { ") { id } }'  # no block string: invalid before a shorthand query
    sdl = SCHEMA_SDL.replace("me: User", 'me(arg: String = ""): User')
    res = analyze(query, sdl)
    assert res.cost == 1


def test_check_passes_under_limits() -> None:
    schema = build_schema(SCHEMA_SDL)
    res = check("{ me { id } }", schema, config=CostConfig(max_cost=10, max_depth=5))
    assert res.cost == 1
    assert res.depth == 2


def test_empty_document_raises_syntax_error() -> None:
    schema = build_schema(SCHEMA_SDL)
    with pytest.raises(CostLimitError) as exc:
        analyze("# only comment", schema)
    assert exc.value.code == "syntax_error"


def test_unknown_fragment_and_type_conditions() -> None:
    schema = build_schema(SCHEMA_SDL)
    q_unknown_frag = "{ me { ...MissingFrag } }"
    with pytest.raises(CostLimitError) as exc:
        analyze(q_unknown_frag, schema)
    assert exc.value.code == "unknown_field"

    q_unknown_type = "fragment F on NonExistentType { id } { me { ...F } }"
    with pytest.raises(CostLimitError) as exc2:
        analyze(q_unknown_type, schema)
    assert exc2.value.code == "unknown_field"

    q_unknown_inline = "{ me { ... on NonExistentType { name } } }"
    with pytest.raises(CostLimitError) as exc3:
        analyze(q_unknown_inline, schema)
    assert exc3.value.code == "unknown_field"


def test_missing_root_type_and_error_message_truncation() -> None:
    sdl = "type Query { me: String }"
    with pytest.raises(CostLimitError) as exc:
        analyze("mutation { doSomething }", sdl)
    assert exc.value.code == "unknown_field"

    # Truncation test
    long_msg = "x" * 300
    err = CostLimitError(long_msg, code="syntax_error")
    assert len(str(err)) == 200

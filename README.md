# graphql-cost-limit

Schema-aware cost and depth limits for GraphQL queries before execution: slicing-argument multipliers, fragment cycle detection, and pre-parse nesting guards.

## Problem

Public GraphQL endpoints accept queries that nest friends of friends ten levels deep or alias the same expensive field a thousand times, and one request pins the database. Depth limits alone miss wide queries, and cost rules differ between servers. This library computes a documented cost and depth for an operation against the schema before execution and raises a typed error when a limit is exceeded.

## Installation

```bash
pip install graphql-cost-limit
```

## Usage

```python
from graphql_cost_limit import analyze, CostConfig

schema = "type Query { users(first: Int): [User!]! } type User { name: String }"
# Calculate analysis
analysis = analyze("{ users(first: 5) { name } }", schema)
print(f"Cost: {analysis.cost}, Depth: {analysis.depth}")
```

## API Summary

- `analyze(query: str, schema: GraphQLSchema | str, *, variables=None, operation_name=None, config=CostConfig()) -> Analysis`: Calculates cost/depth.
- `check(query: str, schema: GraphQLSchema | str, *, variables=None, operation_name=None, config=CostConfig()) -> Analysis`: Same as `analyze`, but raises `CostLimitError` if limits are exceeded.
- `CostConfig` options: `field_costs` (dict), `default_object_cost` (int), `default_leaf_cost` (int), `slicing_arguments` (tuple), `default_list_size` (int), `max_cost` (int), `max_depth` (int), `max_query_chars` (int), `max_nesting` (int).
- `CostLimitError`: Raised for violations (codes: `query_too_large`, `too_deep_nesting`, `syntax_error`, `operation_required`, `unknown_operation`, `fragment_cycle`, `unknown_field`, `invalid_argument`, `max_cost`, `max_depth`).

## Why not depth-only validators?

Wide and aliased queries can be just as expensive as deeply nested ones. This library provides a schema-aware rule set that accounts for both.

See full documentation in [docs/SECURITY.md](docs/SECURITY.md).
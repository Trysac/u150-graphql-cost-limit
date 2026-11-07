# Testing

## Running

```sh
pytest
```

## Coverage

The test suite is located in `tests/test_graphql_cost_limit.py`. It covers the following scenarios:

- Cost and depth calculations for various schema and query combinations (acceptance tests).
- Detection of fragment cycles.
- Handling of unknown fields and fragments.
- Validation of slicing arguments (e.g., non-integer, negative values).
- Pre-parse guards for query length and brace nesting.
- Operation selection and validation (e.g., missing operations, unknown operation names).
- Support for mutations and subscriptions.
- Validation of `max_cost` and `max_depth` limits via `check()`.
# Architecture

`trysac-graphql-cost-limit` provides pre-execution static analysis of GraphQL query documents.

## Execution Phases

1. **Length Guard**: Verifies query string length against `config.max_query_chars`.
2. **Lexical Pre-parse Scanner**: Counts curly braces `{` outside string literals and comments to reject deeply nested documents before invoking parser AST generation.
3. **AST Parsing**: Parses query with `graphql-core` and normalizes schema (via `build_schema` if passed as SDL).
4. **Operation Selection**: Selects targeted operation or validates single operation constraint.
5. **Recursive AST Traversal**:
   - Calculates field cost based on configured overrides, object defaults, or leaf defaults.
   - Resolves slicing argument multipliers for list-wrapped types.
   - Expands fragment spreads and inline fragments with cycle detection.
   - Measures maximum query nesting depth.
6. **Limit Check**: In `check()`, validates `cost <= max_cost` and `depth <= max_depth`, raising `CostLimitError` on violations.

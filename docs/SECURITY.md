# Security notes

## Threat model

`graphql-cost-limit` performs static analysis of GraphQL query strings.

### Defended

- **Resource Exhaustion (Static)**: Maliciously crafted queries designed to be computationally expensive to parse or execute (e.g., deeply nested braces, massive string length) are rejected before full AST generation using pre-parse lexical scans.
- **Infinite Recursion**: Fragment cycles are detected during the recursive AST walk and rejected.
- **Oversized Payloads**: Queries exceeding `max_query_chars` (default 100,000) are rejected immediately.
- **Malformed Queries**: Syntactically invalid queries are rejected with an explicit `syntax_error` code.

### Limits from code

- `max_query_chars`: 100,000 characters.
- `max_nesting`: 100 levels of nested curly braces.

### Not defended

- **Runtime Execution**: This library only performs static analysis. It does not control execution or measure actual database load during query resolution.
- **IO/System Calls**: The library is a pure computation utility and does not perform I/O.
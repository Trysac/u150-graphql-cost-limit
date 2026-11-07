# Project record

## Objective

Schema-aware cost and depth limits for GraphQL queries before execution, specifically handling slicing-argument multipliers, fragment cycle detection, and pre-parse nesting guards.

## Scope

- Implementing pre-execution cost and depth calculation logic.
- Implementing static length and brace-nesting guards to protect the parser.
- Detecting fragment cycles.
- Resolving slicing argument multipliers dynamically from query values.

## Out-of-scope

- Server-side middleware for specific frameworks.
- Persisted query storage.
- Global rate limiting across multiple requests.
- Runtime resolver measurement.

## Effort metrics

| Metric | Value |
|---|---|
| Tokens (input / output) | 1019903 / 14490 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.2462 |

## Factory run u150 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | gemini-3.8-flash | yes | 4360 | 7504 | 0 | 0 | 0.0157 |
| fix-1 | gemini-3.8-flash | no | 32981 | 2838 | 0 | 108652 | 0.0435 |
| fix-2 | gemini-3.8-flash | no | 19239 | 368 | 0 | 32903 | 0.0183 |
| fix-3 | gemini-3.8-flash | no | 77718 | 1940 | 0 | 505666 | 0.1035 |
| fix-4 | gemini-3.8-flash | no | 10691 | 193 | 0 | 6400 | 0.0092 |
| audit | gemini-3.1-flash-lite | no | 31715 | 345 | 0 | 8122 | 0.0086 |
| docs | gemini-3.1-flash-lite | no | 181456 | 1302 | 0 | 0 | 0.0473 |

Total: $0.2462. Prices: Anthropic list prices.

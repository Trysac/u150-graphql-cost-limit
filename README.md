# graphql-cost-limit

[![PyPI version](https://img.shields.io/pypi/v/trysac-graphql-cost-limit)](https://pypi.org/project/trysac-graphql-cost-limit/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-graphql-cost-limit)](LICENSE)
[![CI](https://github.com/Trysac/u150-graphql-cost-limit/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u150-graphql-cost-limit/actions/workflows/ci.yml)

Schema-aware cost and depth limits for GraphQL queries before execution: slicing-argument multipliers, fragment cycle detection and pre-parse nesting guards

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-graphql-cost-limit
# or
uv add trysac-graphql-cost-limit
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import graphql_cost_limit

# normalize() trims surrounding whitespace and lower-cases the text.
print(graphql_cost_limit.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    graphql_cost_limit.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez

# Use graphql-core for Schema and Query AST Traversal

Status: accepted (generated, pending human review)

## Context

A secure and standard-compliant GraphQL cost calculator requires parsing GraphQL SDL and query syntax correctly, including list wrapping, fragment spreads, and composite type definitions.

## Decision

Depend on graphql-core 3.2 for query parsing and schema type inspection while implementing custom pre-parse lexical depth guards and cost accumulation.

## Consequences

Provides robust GraphQL spec adherence and AST modeling without reinventing parser complexity, with negligible overhead.

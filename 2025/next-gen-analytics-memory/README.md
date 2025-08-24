# Next Gen Analytics (Memory)

This directory contains a prototype implementation of a cache-aware
analytics agent built with LangGraph. It demonstrates the overall
architecture described in the project specification, including:

- Deterministic cache keys for SQL queries
- Supervisor driven by cache hit/miss routing
- Placeholder nodes for planning, SQL execution, incremental updates,
  chart rendering and analysis
- Minimal React frontend showing cache metrics and execution path

The implementation is intentionally lightweight and focuses on the
scaffolding required for further development.

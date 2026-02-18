# Project Plan: Code Intelligence MCP Server

## Overview
A lightweight, high-performance MCP server providing semantic code search and AST-aware indexing, optimized for modern AI agents (e.g., Antigravity).

## Architecture
- **Parser**: Tree-sitter (multi-language support).
- **Storage**: LanceDB (local vector storage).
- **Embeddings**: BGE-M3 (via Ollama).
- **Runtime**: Python 3.11+ with `fastmcp`.

## Milestones

### Milestone 1: Core AST Indexing (Completed)
- [x] Basic Tree-sitter integration.
- [x] Semantic chunking logic.
- [x] Multi-language support (Python, JS, TS, etc.).

### Milestone 2: High-Fidelity Metadata & Stability (Completed)
- [x] Advanced AST Parsing for Symbol Recognition.
- [x] Complexity Scoring (Cyclomatic).
- [x] Dependency Analysis (Import Mapping).
- [x] Git History extraction (Author/Date).
- [x] Enhanced `get_stats` with language and architectural insights.
- [x] "Deep Insights" Stats (Dependency Hubs, Test Gaps, Project Pulse).
- [x] Stdout Protection (Fortress) for protocol stability.
- [x] Multi-Project Isolation: Vector storage isolation using project root path hashing.
- [x] Search Visibility: Exposed Author, Date, and Dependencies in search output.
- [x] Optimization of embedding latency via local Ollama caching.

### Milestone 3: Advanced Intelligence (Cross-File & Graph) (Current)
- [ ] **Phase 3.1: Import Resolution Engine**
    - [ ] Implement language-specific import resolvers (Python: `sys.path` logic, JS/TS: `node_modules` + `tsconfig`, Dart: `package:`).
    - [ ] Map "string imports" to "file system paths".
- [ ] **Phase 3.2: Usage & Reference Analysis**
    - [ ] Advanced Tree-sitter queries to find *usages* of symbols (not just definitions).
    - [ ] Link usages to their resolved definitions (The "Jump to Definition" link).
- [ ] **Phase 3.3: Knowledge Graph Persistence**
    - [ ] New storage layer (SQLite "edges" table or graph DB).
    - [ ] Store relationships: `(SourceFile, SourceLine) -> (TargetFile, TargetSymbol)`.
- [ ] **Phase 3.4: "Trace" Tooling**
    - [ ] New tool `find_references(symbol)` and `goto_definition(symbol)`.
- [ ] Integration with more LLM providers.
- [ ] Real-time indexing on file change.

### Milestone 4: Deployment & DX
- [ ] One-click installers/packages.
- [ ] Comprehensive CLI dashboard.

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

### Milestone 3: Advanced Intelligence (Cross-File & Graph) (Completed)

- [x] **Phase 3.1: Import Resolution Engine**
  - [x] Implement language-specific import resolvers (Python: `sys.path` logic, JS/TS: `node_modules` + `tsconfig`, Dart: `package:`).
  - [x] Map "string imports" to "file system paths".
- [x] **Phase 3.2: Usage & Reference Analysis**
  - [x] Advanced Tree-sitter queries to find *usages* of symbols (not just definitions).
- [x] **Phase 3.3: Knowledge Graph Persistence**
  - [x] New storage layer (SQLite "edges" table).
  - [x] Store relationships: `(SourceChunk) -> (TargetChunk)`.
- [x] **Phase 3.4: "Trace" Tooling**
  - [x] New tool `find_references(symbol)` and `find_definition(symbol)`.
- [x] **Phase 3.4.6: Global Symbol Excellence**
  - [x] Index top-level variables and constants (Dart/Python).
  - [x] Enable cross-file navigation for non-structural symbols.
- [x] **Phase 3.5: Domain-Specific Intelligence (Selos Specials)**
  - [x] **Firestore Rules**: Index `match` paths for client-side linking.
  - [x] **Mermaid**: Extract labels from diagrams to link documentation to code.
- [ ] **Phase 3.6: Advanced Linking & Discovery**
  - [ ] **Granular Symbol Mapping**: Link string literals in code to Firestore `match` paths.
  - [ ] **Mermaid "Soft Links"**: Connect diagram node labels to actual class/function definitions.
  - [ ] **Script Discovery**: Implement heuristic linking for standalone scripts (no imports).
  - [ ] **Entry-Point Detection**: Weight files with `main` blocks higher in the Knowledge Graph.
- [ ] Integration with more LLM providers.
- [ ] Real-time indexing on file change.

### Milestone 4: Deployment & DX

- [x] **Verification:** Full suite verification (Rebuild, Search, Stats, Graph) passed on fresh install.
- [x] **Scope Tuning:** Add `include` and `exclude` glob patterns to `search_code` and `refresh_index`.
- [x] **Infrastructure**: Optimized for Windows (CPU fix) and Jina embeddings.
- [x] **Security Hardening**: Remediated findings from audit (SQLi, Pickle, Path Traversal). Added robust sanitization and path containment.
- [x] **Professional Standards**: Added MIT License, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, and `SECURITY.md`.
- [x] **Release Automation**: Implemented GitHub Action for automated releases on version tags.

- [ ] One-click installers/packages.
- [ ] Comprehensive CLI dashboard.

### Milestone 5: Code Quality & Refactoring (In Progress)

- [x] **Wave 1: Quick Wins** (Sorting logic, inline imports, exception handling, config bug).
- [x] **Wave 2: Structural Decomposition** (`server.py` → `src/tools/`, `src/indexer.py`, `src/context.py`; AppContext DI container; 83% test coverage).
- [x] **Wave 3: Performance & Core Refactor** (Strategy Pattern, Persistence, Pass 2 Caching).
- [x] **Wave 4: Production-Grade Scaling** (LanceDB Caching, SQLite Transaction Batching).
- [x] **Wave 5: Secondary Remediation** (Sub-module test normalization, CI security automation).
- [ ] **Wave 6: Enhanced Agent Observability** (Index Metadata & Git Summaries).

### Milestone 6: Agent Navigation & Health

- [ ] **Phase 6.1: Indexing Intelligence**
  - [ ] Persist last index runtime, type, and embedding model in LanceDB.
  - [ ] Add "Codebase Freshness" spot-check metrics.
- [ ] **Phase 6.2: Git Activity Insight**
  - [ ] Integrate latest commit summary and repository "dirty" status into `get_stats`.
- [ ] **Phase 6.3: Architectural Guardian**
  - [ ] Automated 200/50 rule violation reporting for large files/methods.

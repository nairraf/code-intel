# Project Plan: Code Intelligence MCP Server

## Overview

A lightweight, high-performance MCP server providing semantic code search and AST-aware indexing, optimized for modern AI agents (e.g., Antigravity).

## Architecture

- **Parser**: Tree-sitter (multi-language support).
- **Storage**: LanceDB (local vector storage).
- **Embeddings**: Jina Embeddings v2 Base Code via Ollama.
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
- [ ] **Structural Impact Analysis** (Blast Radius for Refactoring).
- [ ] **Deep AST Support for DI frameworks** (FastAPI Depends / Riverpod).

### Milestone 5: Code Quality & Refactoring (In Progress)

- [x] **Wave 1: Quick Wins** (Sorting logic, inline imports, exception handling, config bug).
- [x] **Wave 2: Structural Decomposition** (`server.py` → `src/tools/`, `src/indexer.py`, `src/context.py`; AppContext DI container; 83% test coverage).
- [x] **Wave 3: Performance & Core Refactor** (Strategy Pattern, Persistence, Pass 2 Caching).
- [x] **Wave 4: Production-Grade Scaling** (LanceDB Caching, SQLite Transaction Batching).
- [x] **Wave 5: Secondary Remediation** (Sub-module test normalization, CI security automation).
- [ ] **Wave 6: Enhanced Agent Observability** (Index Metadata & Git Summaries).

### Milestone 6: Agent Navigation & Health

- [x] **Phase 6.1: Indexing Intelligence**
  - [x] Persist last index runtime, type, and embedding model in LanceDB.
  - [x] Add "Codebase Freshness" spot-check metrics.
- [x] **Phase 6.2: Git Activity Insight**
  - [x] Integrate latest commit summary and repository "dirty" status into `get_stats`.
- [x] **Phase 6.3: Architectural Guardian**
  - [x] Automated 200/50 rule violation reporting for large files/methods.

### Milestone 7: Retrieval Precision & Agent Trust

Goal: Increase practical value for AI agents by reducing false-positive discovery, improving dynamic-framework navigation, and making result confidence easier to operationalize.

- [ ] **Phase 7.1: Source-First Retrieval Ranking**
  - [ ] Add ranking priors so implementation files outrank documentation for code-intent queries.
  - [ ] De-prioritize `docs/` and report artifacts unless the query intent is explicitly documentation-oriented.
  - [ ] Surface result classification metadata such as `source`, `test`, `docs`, and `report` in search results.
  - [ ] Add an optional source-biased search mode for agent workflows that need implementation candidates first.
  - [ ] Validate improvements against benchmark queries where documentation currently outranks code.
- [ ] **Phase 7.2: Framework-Aware Reference Semantics**
  - [ ] Expand Python dependency-injection detection for FastAPI-style `Depends` flows.
  - [ ] Classify graph relationships by reference kind: import, call, dependency-injection, decorator, and instantiation.
  - [ ] Improve confidence labeling in reference results so agents can distinguish exact structural matches from heuristic matches.
  - [ ] Add focused regression tests for framework-owned symbols and middleware-style registration paths.
- [ ] **Phase 7.3: Query Intent & Agent Guidance**
  - [ ] Add lightweight query-intent heuristics to distinguish code lookup from architecture/documentation exploration.
  - [ ] Bias semantic retrieval toward source paths when the query expresses implementation intent.
  - [ ] Recommend scoped search patterns when the repository contains high-volume documentation noise.
  - [ ] Expose guidance that helps agents choose between `search_code`, `find_definition`, and `find_references` based on intent.

### Milestone 8: Benchmarking & Decision Support

Goal: Turn external evaluation feedback into a repeatable quality gate that helps decide when tool investment creates enough cross-project value.

- [ ] **Phase 8.1: Repeatable Retrieval Benchmark Suite**
  - [ ] Create benchmark scenarios for definition lookup, reference recall, semantic precision, and documentation-noise suppression.
  - [ ] Capture representative cases from external evaluations as reusable fixtures and expected outcomes.
  - [ ] Add regression coverage for low-confidence Python DI and framework-registration patterns.
- [ ] **Phase 8.2: Agent-Centric Scoring Model**
  - [ ] Score benchmark results by precision, trustworthiness, narrowing effort, and usefulness to downstream agents.
  - [ ] Add reporting that makes it clear which capabilities are safe for first-pass use versus verification-required use.
  - [ ] Track whether improvements reduce follow-up manual search steps for agents.
- [ ] **Phase 8.3: Roadmap Decision Signals**
  - [ ] Define milestone exit criteria for search ranking quality, reference confidence, and benchmark pass thresholds.
  - [ ] Add release-readiness signals that show when the tool is strong enough to justify focused investment over parallel project work.
  - [ ] Summarize benchmark deltas in project status artifacts for easier prioritization reviews.

### Milestone 9: Agent Workflow Enablement

Goal: Make `code-intel` more predictable and more valuable as a default first-step tool for cloud agents operating across unfamiliar repositories.

- [ ] **Phase 9.1: Confidence-Aware Workflow Documentation**
  - [ ] Document a standard two-step workflow: `code-intel` candidate discovery followed by narrow literal verification for heuristic cases.
  - [ ] Add confidence interpretation guidance to help agents decide when direct action is safe.
  - [ ] Publish query cookbook examples for Python, Dart, and mixed documentation-heavy repositories.
- [ ] **Phase 9.2: Path Scoping & Workflow Ergonomics**
  - [ ] Make include/exclude scoping more discoverable in user-facing docs and examples.
  - [ ] Add examples that bias search to implementation directories before broad repository exploration.
  - [ ] Highlight best-practice workflows for code changes, impact analysis, and architectural reconnaissance.
- [ ] **Phase 9.3: Cross-Project Value Packaging**
  - [ ] Identify which improvements most reduce agent uncertainty across non-trivial repositories.
  - [ ] Document reusable patterns for teams adopting `code-intel` in other codebases.
  - [ ] Tie documentation updates to benchmark-backed claims so positioning remains evidence-based.

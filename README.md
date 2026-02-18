# Code Intelligence MCP Server 🧠🚀

A lightweight, high-performance Model Context Protocol (MCP) server that provides semantic code search and AST-aware indexing for your AI agents. Powered by **Tree-sitter** for intelligent parsing and **LanceDB** for local vector storage.

## 🌟 Key Features

### 1. Stdout Fortress 🏰
Rigorous stdout protection ensures the MCP protocol is never corrupted by library background noise.
- **Redirection**: All `print()` calls are automatically forced to `stderr`.
- **Integrity**: Standardized JSON-RPC stream for 100% reliability in Antigravity.

### 2. Multi-Project Isolation 🛡️
Strict isolation for multiple concurrent projects:
- **Per-Project Tables**: Each project gets a unique table in a central database based on its root path hash.
- **Zero Conflict**: Run multiple agents on different projects without write-lock contention.
- **Unified Store**: All data lives centrally in `~/.code_intel_store/`, keeping your project repos clean.

- **Language Support**: Python, JS, TS, HTML, CSS, Go, Rust, Java, C++, Dart, SQL, **Firestore Rules**.
- **Specialized Parsers**:
    - **Firestore**: Extracts security rule `match` paths as searchable symbols.
    - **Mermaid**: Extracts node labels from diagrams in Markdown to link docs to code.

### 4. Cross-File Symbol Intelligence 🧭
- **Jump to Definition**: Precisely locate the source of any function, class, or variable across the entire project.
- **Find References**: Track all call sites and usages of a specific symbol for safe refactorings.
- **Knowledge Graph**: Persists relationships (call, import, inheritance) in a local SQLite graph for fast traversal.
- **Import Resolution Engine**: Language-specific logic (Python, TS/JS, Dart) to map standard imports to physical files.

### 5. Git Integration & Stability ⚡
- **Authorship Tracking**: Automatically extracts author and last-modified timestamps for every code chunk.
- **Project Pulse**: Real-time reporting of the active branch and count of stale files (>30 days).
- **Parallel Git Fetching**: Uses a strict semaphore (max 10) for parallel git subprocesses to ensure stability on Windows.
- **Async Pipeline**: Fully asynchronous file scanning and indexing.

### 6. GPU-Ready Vector Search 🚀
- **BGE-M3 (1024 dims)**: Uses the state-of-the-art embedding model via **Ollama**.
- **LanceDB**: Local-first vector storage for sub-millisecond query performance.

### 7. Performance & Incremental Indexing ⚡
- **SHA-256 Hashing**: Content-based change detection ensures only modified files are processed.
- **Incremental Mode**: Significantly reduces re-indexing time by skipping unchanged files.
- **Cross-Platform Consistency**: Unified forward-slash path handling for reliable hashing on Windows.

---

## 🚀 Available Tools

| Tool | Description |
|:---|:---|
| `refresh_index` | Scans and indexes the project. Rebuilds semantic index and Knowledge Graph symbols. |
| `search_code` | Semantic search with complexity, dependency, and git metadata insights. |
| `get_stats` | Architectural overview: High-Risk symbols, Dependency Hubs, Test Gaps, and Pulse. |
| `find_definition` | Precise jump-to-definition for symbols across files. |
| `find_references` | Finds all usages and call sites of a symbol in the project. |

---

## 🛠️ Configuration

| Setting | Default | Description |
|:---|:---|:---|
| **EMBEDDING_MODEL** | `bge-m3:latest` | High-precision multi-lingual embeddings. |
| **STORAGE_ROOT** | `~/.code_intel_store/db` | Centralized vector storage location. |
| **LOG_ROOT** | `~/.code_intel_store/logs` | Centralized server logs. |

---

## 🧪 Testing

```bash
# Run all tests
uv run pytest tests/

# Run specific test
uv run pytest tests/test_isolation.py
```

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

### 3. Smart AST Parsing 🌳
- **Semantic Chunking**: Uses Tree-sitter to intelligently extract functions and classes instead of blind text slicing.
- **Language Support**: Python, JS, TS, HTML, CSS, Go, Rust, Java, C++, Dart, SQL.

### 4. Performance & Stability ⚡
- **Async Indexing**: Fully asynchronous pipeline for file scanning and git metadata lookup.
- **Parallel Git Fetching**: Uses a strict semaphore (max 10) for parallel git subprocesses to ensure stability on Windows.
- **Persistent Connections**: Reuses embedding client connections for significantly lower latency.
- **Unified Concurrency**: Global inference semaphore (max 5) prevents local LLM overload during batch processing.

### 5. GPU-Ready Vector Search 🚀
- **BGE-M3 (1024 dims)**: Uses the state-of-the-art embedding model via **Ollama**.
- **LanceDB**: Local-first vector storage for sub-millisecond query performance.

---

## 🚀 Available Tools

| Tool | Description |
|:---|:---|
| `refresh_index` | Scans and indexes the project. Use `force_full_scan=True` to wipe/rebuild. |
| `search_code` | Performs a semantic search within the specified project context. |
| `get_stats` | Returns current index statistics (chunk count) without re-scanning. |

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

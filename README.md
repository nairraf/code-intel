# Cognee Memory MCP Server (v2.0.0) 🧠🚀

A production-grade Model Context Protocol (MCP) server that brings persistent, high-performance knowledge graphs to your AI agent. Powered by **Cognee** and optimized for **Local GPU (Ollama)**.

## 🌟 Key Features

### 1. Protocol Shield 🛡️
Advanced filtering logic separates library background noise from the MCP protocol.
- **Fortress**: FD-level stdout redirect ensures zero protocol corruption.
- **Silencing**: Noisy loggers set to `ERROR` by default.
- **Handler Stripping**: Dynamically removes rogue `stdout` handlers at runtime.

### 2. Multi-Project Vault Isolation
Each project gets its own local `.cognee_vault/` directory:
- **Local Vaults**: Created at each project's root (add `.cognee_vault/` to `.gitignore`).
- **Isolated Logs**: Project-specific logs in a central `logs/` directory.
- **Dynamic Context**: Automatically switches databases based on the `project_path` parameter.
- **Concurrency Safety**: Per-project `asyncio.Lock` prevents operation collisions.

### 3. GPU Accelerated Pipeline
- **Qwen3-Embedding (0.6b)**: 32k context, 2048-token chunks.
- **Dimension Validation**: Embeddings are validated against expected dimensions with retries.
- **Sequential Extraction**: `chunks_per_batch=1` for SQLite stability.

---

## 🚀 Available Tools

All tools support an optional `project_path` parameter for vault isolation.

| Tool | Description |
|:---|:---|
| `sync_project_memory` | Ingests codebase into `.cognee_vault`. Does nuclear reset + fresh sync. |
| `search_memory` | Queries the knowledge graph (`GRAPH_COMPLETION` or `CODE`). |
| `check_memory_status` | Returns project stats, disk usage, and Ollama status. |
| `prune_memory` | Nuclear reset — removes all vault internals and database locks. |

### Sync Strategy

Every `sync_project_memory` call does a **full nuclear reset** before syncing:
1. Removes `.cognee_system/` and `.data_storage/` via `shutil.rmtree`
2. Re-initializes Cognee configuration for fresh paths
3. Ingests source files and builds knowledge graph

This ensures zero lock contention and clean database state.

### Supported File Types

`.py`, `.md`, `.txt`, `.json`, `.yaml`, `.yml`, `.toml`, `.js`, `.ts`, `.tsx`, `.jsx`, `.css`, `.html`, `.sh`, `.sql`, `.dart`

---

## 🛠️ Configuration

| Setting | Value | Description |
|:---|:---|:---|
| **LLM_MODEL** | `qwen2.5-coder:7b` | Default reasoning model. |
| **EMBEDDING_MODEL** | `qwen3-embedding:0.6b` | High-precision local embeddings. |
| **EMBEDDING_DIMENSIONS** | `1024` | Expected vector size (validated). |
| **SYSTEM_ROOT** | `.cognee_vault/.cognee_system` | Isolated metadata storage. |
| **DATA_ROOT** | `.cognee_vault/.data_storage` | Raw ingested data storage. |

---

## 🧪 Testing

```bash
uv run pytest tests/ -v
```

With coverage:
```bash
uv run pytest --cov=mcp_cognee tests/
```

# Cognee Memory MCP Server (v1.2.5) 🧠🚀

A production-grade Model Context Protocol (MCP) server that brings persistent, high-performance knowledge graphs to your AI agent. Powered by **Cognee** and optimized for **Local GPU (Ollama)**.

## 🌟 Key Features

### 1. Protocol Shield 🛡️
Advanced filtering logic separates library background noise from the MCP protocol. This prevents the "invalid character" errors common in complex Python library integrations.
- **Redirection**: All startup output and dependency prints are diverted to `stderr`.
- **Silencing**: Noisy loggers (httpx, instructor, etc.) are set to `ERROR` level by default.
- **Aggressive Stripping**: Dynamically removes rogue log handlers attached to `stdout` at runtime.

### 2. Multi-Project Support & Vault Isolation
The server automatically detects your project identity and creates a local repository for memories:
- **Vault Location**: `.cognee_vault/` is created at your project's root.
- **Isolated Logs**: Project-specific logs are stored in the central `logs/` directory (e.g., `agentic_env.log`, `selos.log`).
- **Dynamic Context**: Automatically switches databases and paths based on the `project_path` parameter or current environment.

### 3. GPU Accelerated Pipeline
- **Qwen3-Embedding (0.6b)**: Optimized for 32k context, enabling massive **2048-token chunks**.
- **Sequential Extraction**: Forces `chunks_per_batch=1` to ensure SQLite stability on concurrent local systems.

---

## 🚀 Available Tools

All tools support an optional `project_path` parameter to ensure correct vault isolation.

- `sync_project_memory(project_path: str = None)`: Ingests the codebase into the local `.cognee_vault`.
- `search_memory(query: str, search_type: str, project_path: str = None)`: Query the knowledge graph.
- `check_memory_status(project_path: str = None)`: Live project stats and disk usage.
- `prune_memory(project_path: str = None)`: Deep clean for the project vault and database unlock.

---

## 🛠️ Configuration

The MCP server respects your environment but provides dynamic defaults for pathing.

| Setting | Value | Description |
| :--- | :--- | :--- |
| **LLM_MODEL** | `qwen2.5-coder:7b` | Default reasoning model. |
| **EMBEDDING_MODEL** | `qwen3-embedding:0.6b` | High-precision local embeddings. |
| **SYSTEM_ROOT** | `.cognee_vault/.cognee_system` | Isolated metadata storage. |
| **DATA_ROOT** | `.cognee_vault/.data_storage` | Raw ingested data storage. |

---

## 🧪 Verification & Testing

Verify system stability and protocol shielding using the comprehensive test suite:

```bash
uv run pytest tests/
```

To view code coverage:
```bash
uv run pytest --cov=mcp_cognee tests/
```

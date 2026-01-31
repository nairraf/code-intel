# Cognee Memory MCP Server (v1.1.0) 🧠🚀

A production-grade Model Context Protocol (MCP) server that brings persistent, high-performance knowledge graphs to your AI agent. Powered by **Cognee** and optimized for **Local GPU (Ollama)**.

## 🌟 Key Features

### 1. High-Performance Embedding Pipeline
- **Qwen3-Embedding (0.6b)**: Optimized for 32k context, enabling massive **2048-token chunks** for higher precision.
- **GPU Accelerated**: Fully multi-threaded and sequential processing to prevent local LLM bottlenecking.

### 2. Multi-Project Support
The server automatically detects your project identity and isolates data:
- **Flutter/Dart**: Uses `pubspec.yaml` name.
- **Node.js/Web**: Uses `package.json` name.
- **General**: Falls back to directory name or `.git` identity.
- **Vault Location**: All memories are stored in a centralized, project-isolated directory: `D:\Development\ALL_COGNEE_MEMORIES`.

### 3. Protocol Shield 🛡️
Advanced filtering logic separates library background noise from the MCP protocol. This prevents the "invalid character" errors common in complex Python library integrations.

### 4. Live Vault Metrics
Track your local knowledge growth with the `check_memory_status` tool:
- Live disk usage in MB.
- Internal database/graph file count.
- Health check for local Ollama.

---

## 🛠️ Performance Configuration

The following settings are pre-configured for the best balance of speed and VRAM usage on a 6GB+ GPU:

| Setting | Value | Why? |
| :--- | :--- | :--- |
| **LLM_MODEL** | `qwen2.5-coder:7b` | High-quality reasoning. |
| **EMBEDDING_MODEL** | `qwen3-embedding:0.6b` | 1024-dim accuracy. |
| **CHUNK_SIZE** | `2048` | Larger context for better RAG. |
| **WINDOW_CONTEXT** | `8192` | Forced via monkeypatch for embeddings. |

---

## 🚀 Available Tools

- `sync_project_memory`: Ingests the current codebase into the vault.
- `search_memory`: Query the knowledge graph (GRAPH_COMPLETION or CODE).
- `check_memory_status`: Live project stats and health.
- `prune_memory`: Deep clean for the current project vault.

---

## 🧪 Verification
Run unit tests to verify project identity logic:
```bash
.venv\Scripts\python tests/test_mcp_logic.py
```

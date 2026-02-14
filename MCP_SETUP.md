# Setting up Code Intelligence MCP

To give your Antigravity agent semantic search capabilities across your projects, add the `code-intel` server.

## 1. Configuration

Add the following to your Antigravity MCP configuration:

```json
{
  "mcpServers": {
    "code-intel": {
      "command": "uv",
      "args": [
        "run",
        "--quiet",
        "--no-progress",
        "--directory",
        "d:/Development/agentic_env",
        "python",
        "-m",
        "src.server"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

## 2. Usage Policy

The server is **Project Isolated**. Each time you use the tools, the agent handles the indexing context for you.

### Typical Workflow

1.  **Indexing**: Run `refresh_index(root_path=".")` to build the semantic map. Use `force_full_scan=True` to rebuild from scratch.
2.  **Searching**: Use `search_code(query="how is auth implemented?")` to retrieve relevant code blocks from that specific project.

## 3. Storage & Logs

- **Data Partitioning**: All project data is stored in `~/.code_intel_store/db/`.
- **Troubleshooting**: Check `~/.code_intel_store/logs/server.log` if the server encounters issues.

> [!TIP]
> Ensure **Ollama** is running with `bge-m3:latest` pullled for optimal performance.

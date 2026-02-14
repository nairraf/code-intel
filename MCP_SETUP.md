# Setting up Cognee MCP Server

To give an Antigravity agent access to your project's local memory, add the `mcp_cognee.py` script as an MCP Server.

## 1. Configuration

Add the following to your MCP Client configuration (**Settings** > **MCP Servers** or `mcp_server_config.json`):

```json
{
  "mcpServers": {
    "cognee-memory": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "d:/Development/agentic_env",
        "python",
        "mcp_cognee.py"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

> [!NOTE]
> Ensure `uv` is in your system PATH. If not, use the full path to the `uv` executable.

## 2. Restart/Reload
After saving the configuration, **restart Antigravity** or reload the MCP servers.

## 3. Available Tools

| Tool | Description |
|:---|:---|
| `sync_project_memory(project_path)` | Ingests codebase and builds knowledge graph. |
| `search_memory(query, search_type, project_path)` | Queries the knowledge graph. |
| `check_memory_status(project_path)` | Returns project stats and Ollama status. |
| `prune_memory(project_path)` | Nuclear reset of vault internals. |

## 4. Multi-Project Usage

Each project gets its own `.cognee_vault/` directory. Pass `project_path` to target a specific project:

```
sync_project_memory(project_path="d:/Development/selos")
search_memory(query="authentication flow", project_path="d:/Development/selos")
```

> [!IMPORTANT]
> Add `.cognee_vault/` to each project's `.gitignore`.

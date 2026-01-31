# Setting up Cognee MCP Server

To give me (Antigravity) access to your project's local memory, you need to add the `mcp_cognee.py` script as an MCP Server.

## 1. Configuration

Add the following to your MCP Client configuration (usually found in **Settings** > **MCP Servers** or `mcp_server_config.json`):

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
After saving the configuration, you may need to **restart Antigravity** or reload the MCP servers for the changes to take effect.

## 3. How I Will Test It
Once the server is connected, I will see new tools available in my toolkit:
- `sync_project_memory`
- `search_memory`
- `check_memory_status`

I will perform the following verification steps:
1.  **Call `check_memory_status`**: To confirm I can talk to the server and see the correct vault path.
2.  **Call `sync_project_memory`**: To index this current repository (`d:/Development/agentic_env`).
3.  **Call `search_memory`**: To ask a question about the project (e.g., "What is the project identity logic?") and verify I get a relevant answer from the local vector store.

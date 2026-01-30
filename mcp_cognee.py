import os
from pathlib import Path
from dotenv import load_dotenv

# 1. Clear out Azure/OpenAI to ensure NO leak
for key in ["AZURE_OPENAI_API_KEY", "OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"]:
    os.environ.pop(key, None)

# 2. Hard-code the local providers for your 7800XT
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["LLM_MODEL"] = "qwen2.5-coder:7b"
os.environ["LLM_ENDPOINT"] = "http://localhost:11434/v1"

# Embedding Config
os.environ["EMBEDDING_PROVIDER"] = "fastembed"
os.environ["EMBEDDING_MODEL"] = "BAAI/bge-small-en-v1.5"
os.environ["EMBEDDING_DIMENSIONS"] = "384"

# Tokenizer is mandatory for local Ollama/FastEmbed setups
os.environ["HUGGINGFACE_TOKENIZER"] = "BAAI/bge-small-en-v1.5"

import asyncio
import cognee
from fastmcp import FastMCP
from cognee.modules.search.types import SearchType

# --- CONFIGURATION ---
CENTRAL_MEMORY_VAULT = Path("D:/Development/ALL_COGNEE_MEMORIES")
CENTRAL_MEMORY_VAULT.mkdir(parents=True, exist_ok=True)

# 1. Initialize the MCP Server
mcp = FastMCP("CogneeMemory")

def find_project_identity():
    """
    Climbs up from CWD to find the project root and identity.
    Returns: (project_id, project_root_path)
    """
    current_path = Path(os.getcwd()).resolve()

    # Climb up to find a root marker (.git, pubspec.yaml, .env)
    project_root = current_path
    for parent in [current_path] + list(current_path.parents):
        if (parent / ".git").exists() or (parent / "pubspec.yaml").exists() or (parent / ".env").exists():
            project_root = parent
            break

    # Try to get the name from pubspec.yaml (Flutter specific) for maximum accuracy
    pubspec = project_root / "pubspec.yaml"
    if pubspec.exists():
        try:
            with open(pubspec, "r") as f:
                for line in f:
                    if line.startswith("name:"):
                        return line.split(":")[1].strip(), project_root
        except:
            pass

    # Fallback to the name of the root directory
    return project_root.name, project_root

def load_cognee_context():
    """Wires up Cognee to the correct project vault and loads env vars."""
    # print(f"DEBUG: Current LLM Provider is {os.getenv('LLM_PROVIDER')}")
    project_id, project_root = find_project_identity()

    # Load .env from project root if it exists
    root_env = project_root / ".env"
    if root_env.exists():
        load_dotenv(root_env, override=True)

    # Route the database to the central vault
    project_vault_path = CENTRAL_MEMORY_VAULT / project_id
    project_vault_path.mkdir(parents=True, exist_ok=True)

    os.environ["COGNEE_SYSTEM_PATH"] = str(project_vault_path)

    return project_id, project_vault_path

@mcp.tool()
async def sync_project_memory():
    """
    Analyzes the current codebase, extracts a knowledge graph, and updates vectors.
    Run this after changing architecture, adding files, or modifying logic.
    """
    project_id, vault = load_cognee_context()
    _, project_root = find_project_identity()

    try:
        # Step 1: Ingest the current root directory
        # Cognee intelligently skips ignored files/folders internally
        # Use the project_id as the dataset name to keep things isolated
        await cognee.add(str(project_root), dataset_name=project_id)

        # Step 2: Cognify (Process graph and vectors)
        await cognee.cognify()

        return f"✅ Memory synced for '{project_id}'. Data stored in vault."
    except Exception as e:
        return f"❌ Sync failed for {project_id}: {str(e)}"

@mcp.tool()
async def search_memory(query: str, search_type: str = "GRAPH_COMPLETION"):
    """
    Searches project memory. 
    Use 'GRAPH_COMPLETION' for high-level logic/architecture questions.
    Use 'CODE' for finding specific snippets or implementations.
    """
    load_cognee_context()
    try:
        # Convert string to Cognee SearchType Enum
        s_type = getattr(SearchType, search_type.upper(), SearchType.GRAPH_COMPLETION)

        results = await cognee.search(query_text=query, query_type=s_type)

        if not results:
            return "No relevant information found in memory."
   
        return results
    except Exception as e:
        return f"❌ Search failed: {str(e)}"

@mcp.tool()
async def check_memory_status():
    """Returns the current project being indexed and its storage location."""
    project_id, vault = load_cognee_context()
    return {
        "active_project": project_id,
        "vault_location": str(vault),
        "environment": "Production-Ready Cognee"
    }

if __name__ == "__main__":
    mcp.run()
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import cognee
from fastmcp import FastMCP
from cognee.modules.search.types import SearchType
import httpx

# --- CONFIGURATION ---
CENTRAL_MEMORY_VAULT = Path("D:/Development/ALL_COGNEE_MEMORIES")
CENTRAL_MEMORY_VAULT.mkdir(parents=True, exist_ok=True)

# 1. Initialize the MCP Server
mcp = FastMCP("CogneeMemory")

async def check_ollama():
    """Verify Ollama is awake and the model is loaded."""
    # print("📡 Checking Ollama connection...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:11434/api/tags", timeout=5.0)
            if response.status_code == 200:
                # print("✅ Ollama is online.")
                return True
    except Exception:
        # print("❌ ERROR: Ollama is not running on localhost:11434")
        return False
    return False

def configure_environment():
    """Sets up the necessary environment variables for Cognee."""
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

def find_project_identity():
    """
    Climbs up from CWD to find the project root and identity.
    Returns: (project_id, project_root_path)
    """
    current_path = Path(os.getcwd()).resolve()

    # Climb up to find a root marker (.git, pubspec.yaml, .env, pyproject.toml)
    project_root = current_path
    markers = [".git", "pubspec.yaml", ".env", "pyproject.toml"]
    
    for parent in [current_path] + list(current_path.parents):
        if any((parent / marker).exists() for marker in markers):
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
    # Sanitize the name to be safe for directory names
    return project_root.name.strip(), project_root

def load_cognee_context():
    """Wires up Cognee to the correct project vault and loads env vars."""
    configure_environment()
    
    project_id, project_root = find_project_identity()

    # Load .env from project root if it exists
    root_env = project_root / ".env"
    if root_env.exists():
        load_dotenv(root_env, override=True)

    # Route the database to the central vault
    project_vault_path = CENTRAL_MEMORY_VAULT / project_id
    project_vault_path.mkdir(parents=True, exist_ok=True)

    os.environ["COGNEE_SYSTEM_PATH"] = str(project_vault_path)
    # Important: Cognee might need re-initialization if paths change, 
    # but setting env var before operation usually works for the *next* import/call usage
    # if cognee internals lazy-load config. 

    return project_id, project_vault_path, project_root

@mcp.tool()
async def sync_project_memory():
    """
    Analyzes the current codebase, extracts a knowledge graph, and updates vectors.
    Run this after changing architecture, adding files, or modifying logic.
    """
    if not await check_ollama():
        return "❌ Sync failed: Ollama is not running on localhost:11434."

    project_id, vault, project_root = load_cognee_context()

    try:
        # Step 1: Ingest the current root directory
        # Cognee intelligently skips ignored files/folders internally (respects .gitignore)
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
    if not await check_ollama():
        return "❌ Search failed: Ollama is not running on localhost:11434."

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
    project_id, vault, _ = load_cognee_context()
    ollama_status = "Online" if await check_ollama() else "Offline"
    return {
        "active_project": project_id,
        "vault_location": str(vault),
        "ollama_status": ollama_status,
        "environment": "Production-Ready Cognee"
    }

if __name__ == "__main__":
    # Windows-specific fix for the "Proactor" event loop
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Run a quick self-check on startup
    print("🚀 Cognee MCP Server Starting...")
    asyncio.run(check_ollama())
    
    mcp.run()